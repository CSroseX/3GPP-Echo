"""Public HTTP API for the demo: ask a question, read the budget, health check.

    uvicorn src.api.main:app --port 8000

The graph is the same one the eval runner and verify.py use; this module only
turns HTTP requests into graph runs. Questions run one at a time (a lock
around the graph), which is what a 2-vCPU free host can serve anyway.

/api/ask returns one JSON answer. /api/ask/stream returns the same answer as
Server-Sent Events: `start` (the question got the graph), one `node` event
per finished node (src/api/events.py), then `done` (the AskResponse) or
`error` ({code, message}).

Budget protection (src/api/quota.py): GET /api/quota issues a visitor token
and reports questions left; both ask endpoints refuse with 429
`quota_exhausted` once the visitor's (or IP's) daily limit is used, and
charge only questions that reached the LLM.
"""

from __future__ import annotations

import queue
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional

import httpx
import openai
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.events import node_facts, sse
from src.api.quota import Quota, default_quota, reached_llm
from src.config import get_settings
from src.obs.logging import get_logger
from src.obs.tracing import trace_attributes, trace_query, update_trace_attributes

log = get_logger(__name__)


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


class Source(BaseModel):
    spec_id: Optional[str] = None
    version: Optional[str] = None
    clause_id: Optional[str] = None
    clause_title: Optional[str] = None
    chunk_type: Optional[str] = None
    excerpt: str = ""


class AskResponse(BaseModel):
    answer: str
    # answered | partial | not_covered | no_answer | out_of_domain
    status: Optional[str]
    cached: bool
    sources: List[Source]
    # Questions the visitor has left today; None when the quota is off.
    questions_left: Optional[int] = None


def _default_graph():
    """Load the retriever (two models) and compile the graph with the answer cache."""
    from src.generation.answer_cache import AnswerCache
    from src.generation.centroids import fastembed_embedder
    from src.generation.graph import build_graph
    from src.retrieval.retriever import Retriever

    cfg = get_settings()
    retriever = Retriever()
    cache = AnswerCache(cfg.project_root / cfg.answer_cache_path, embed=fastembed_embedder(retriever.model))
    return build_graph(retriever=retriever, answer_cache=cache)


def openrouter_balance() -> Optional[float]:
    """Spendable OpenRouter budget in USD, or None if it can't be read.

    The key's own credit limit when one is set (that is what stops the demo),
    capped by the account balance; just the account balance otherwise.
    """
    cfg = get_settings()
    if not cfg.open_router_api_key:
        return None
    headers = {"Authorization": f"Bearer {cfg.open_router_api_key}"}
    try:
        credits = httpx.get(f"{cfg.openrouter_base_url}/credits", headers=headers, timeout=10)
        credits.raise_for_status()
        c = credits.json()["data"]
        account = float(c["total_credits"]) - float(c["total_usage"])
        try:
            key = httpx.get(f"{cfg.openrouter_base_url}/key", headers=headers, timeout=10)
            key.raise_for_status()
            key_left = key.json()["data"].get("limit_remaining")
        except Exception as e:  # no key limit readable: fall back to the account
            log.warning("api.key_limit_unavailable", error=str(e))
            key_left = None
        left = account if key_left is None else min(account, float(key_left))
        return round(left, 4)
    except Exception as e:  # the quota panel must not break the app
        log.warning("api.balance_unavailable", error=str(e))
        return None


def _source(chunk: Dict[str, Any], excerpt_chars: int) -> Source:
    content = chunk.get("content", "")
    # Table chunks keep their raw 2D grid; flatten it for the excerpt.
    if isinstance(content, list):
        content = "\n".join(" | ".join(str(cell) for cell in row) for row in content)
    return Source(
        spec_id=chunk.get("spec_id"),
        version=chunk.get("version"),
        clause_id=chunk.get("clause_id"),
        clause_title=chunk.get("clause_title"),
        chunk_type=chunk.get("chunk_type"),
        excerpt=str(content)[:excerpt_chars],
    )


class ApiError(Exception):
    """An error with an HTTP status and a visitor-facing {code, message}."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message

    def detail(self) -> Dict[str, str]:
        return {"code": self.code, "message": self.message}


def _api_error(e: Exception) -> ApiError:
    """Map a failure inside a graph run to what the visitor is told."""
    if isinstance(e, openai.APIStatusError):
        if e.status_code == 402:
            log.warning("api.budget_exhausted")
            return ApiError(503, "budget_exhausted", "The demo's question budget is used up.")
        log.error("api.llm_error", status=e.status_code, error=str(e))
        return ApiError(502, "llm_error", "The language model is unavailable.")
    log.error("api.ask_failed", error=repr(e))
    return ApiError(500, "internal_error", "Something went wrong.")


def client_ip(request: Request) -> Optional[str]:
    """The visitor's IP: first X-Forwarded-For hop behind the host's proxy."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


QUOTA_EXHAUSTED = {
    "code": "quota_exhausted",
    "message": "You've used today's questions. Come back tomorrow, or try the example questions.",
}


def create_app(
    graph_factory: Callable[[], Any] = _default_graph,
    balance: Callable[[], Optional[float]] = openrouter_balance,
    quota_factory: Callable[[], Quota] = default_quota,
) -> FastAPI:
    cfg = get_settings()
    limits = quota_factory()
    state: Dict[str, Any] = {"graph": None, "started": time.monotonic(), "startup_s": None}
    graph_lock = threading.Lock()
    # "at" None = never fetched (monotonic time can start near 0 on a fresh host).
    budget_cache: Dict[str, Any] = {"value": None, "at": None}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        t0 = time.monotonic()
        state["graph"] = graph_factory()
        state["startup_s"] = round(time.monotonic() - t0, 1)
        log.info("api.ready", startup_s=state["startup_s"])
        yield

    app = FastAPI(title="3GPP-Echo API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.api_cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "startup_s": state["startup_s"],
            "uptime_s": round(time.monotonic() - state["started"], 1),
        }

    @app.get("/api/quota")
    def quota(request: Request, x_visitor_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
        now = time.monotonic()
        if budget_cache["at"] is None or now - budget_cache["at"] > cfg.api_budget_cache_seconds:
            budget_cache["value"] = balance()
            budget_cache["at"] = now
        remaining = budget_cache["value"]
        # A missing or forged token gets a fresh one; the browser stores it.
        token = x_visitor_token if limits.visitor(x_visitor_token) else limits.new_token()
        status = limits.check(limits.visitor(token), client_ip(request))
        return {
            "budget_remaining_usd": remaining,
            "budget_exhausted": remaining is not None and remaining <= 0,
            "visitor_token": token,
            "questions_left": status.left,
            "questions_per_day": status.limit,
        }

    def clean_question(req: AskRequest) -> str:
        question = req.question.strip()
        if not question:
            raise HTTPException(422, detail={"code": "empty_question", "message": "Please type a question."})
        if len(question) > cfg.api_max_question_chars:
            raise HTTPException(
                422,
                detail={
                    "code": "question_too_long",
                    "message": f"Please keep questions under {cfg.api_max_question_chars} characters.",
                },
            )
        return question

    def to_response(final: Dict[str, Any], questions_left: Optional[int]) -> AskResponse:
        log.info("api.answered", status=final.get("termination_reason"), cached=bool(final.get("cache_hit")))
        return AskResponse(
            answer=final.get("answer") or "",
            status=final.get("termination_reason"),
            cached=bool(final.get("cache_hit")),
            sources=[_source(c, cfg.api_source_excerpt_chars) for c in final.get("chunks") or []],
            questions_left=questions_left,
        )

    def settle(final: Dict[str, Any], visitor: Optional[str], ip: Optional[str], left_before: Optional[int]) -> Optional[int]:
        """Charge the question if it reached the LLM; return questions left."""
        if reached_llm(final):
            return limits.charge(visitor, ip)
        return left_before

    @app.post("/api/ask", response_model=AskResponse)
    def ask(req: AskRequest, request: Request, x_visitor_token: Optional[str] = Header(default=None)) -> AskResponse:
        question = clean_question(req)
        visitor, ip = limits.visitor(x_visitor_token), client_ip(request)
        if not limits.check(visitor, ip).allowed:
            raise HTTPException(429, detail=QUOTA_EXHAUSTED)
        try:
            with graph_lock, trace_query(question):
                status = limits.check(visitor, ip)  # again, inside the lock: parallel requests can't slip past
                if not status.allowed:
                    raise HTTPException(429, detail=QUOTA_EXHAUSTED)
                final = state["graph"].invoke({"query": question})
                update_trace_attributes(**trace_attributes(final))
                left = settle(final, visitor, ip, status.left)
        except HTTPException:
            raise
        except Exception as e:
            err = _api_error(e)
            raise HTTPException(err.status, detail=err.detail())
        return to_response(final, left)

    @app.post("/api/ask/stream")
    def ask_stream(
        req: AskRequest, request: Request, x_visitor_token: Optional[str] = Header(default=None)
    ) -> StreamingResponse:
        question = clean_question(req)  # bad input is a plain 422, before any stream
        visitor, ip = limits.visitor(x_visitor_token), client_ip(request)
        if not limits.check(visitor, ip).allowed:
            raise HTTPException(429, detail=QUOTA_EXHAUSTED)
        events: "queue.Queue[Optional[str]]" = queue.Queue()

        def run() -> None:
            # One worker thread owns the whole run, so the lock and the trace
            # context stay on a single thread while events flow to the client.
            try:
                with graph_lock, trace_query(question):
                    status = limits.check(visitor, ip)  # again, inside the lock
                    if not status.allowed:
                        events.put(sse("error", QUOTA_EXHAUSTED))
                        return
                    events.put(sse("start", {}))
                    final: Dict[str, Any] = {"query": question}
                    t = time.monotonic()
                    for chunk in state["graph"].stream({"query": question}, stream_mode="updates"):
                        for node, update in chunk.items():
                            now = time.monotonic()
                            update = update or {}
                            final.update(update)
                            events.put(sse("node", {
                                "node": node,
                                "ms": round((now - t) * 1000),
                                "facts": node_facts(node, update),
                            }))
                            t = now
                    update_trace_attributes(**trace_attributes(final))
                    left = settle(final, visitor, ip, status.left)
                events.put(sse("done", to_response(final, left).model_dump()))
            except Exception as e:
                events.put(sse("error", _api_error(e).detail()))
            finally:
                events.put(None)

        threading.Thread(target=run, daemon=True).start()

        def stream():
            while (item := events.get()) is not None:
                yield item

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
