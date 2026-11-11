"""Public HTTP API for the demo: ask a question, read the budget, health check.

    uvicorn src.api.main:app --port 8000

The graph is the same one the eval runner and app.py use; this module only
turns HTTP requests into graph runs. Questions run one at a time (a lock
around the graph), which is what a 2-vCPU free host can serve anyway.

/api/ask returns one JSON answer. /api/ask/stream returns the same answer as
Server-Sent Events: `start` (the question got the graph), one `node` event
per finished node (src/api/events.py), then `done` (the AskResponse) or
`error` ({code, message}).
"""

from __future__ import annotations

import queue
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional

import httpx
import openai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.events import node_facts, sse
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
    """Remaining OpenRouter credit in USD, or None if it can't be read."""
    cfg = get_settings()
    if not cfg.open_router_api_key:
        return None
    try:
        r = httpx.get(
            f"{cfg.openrouter_base_url}/credits",
            headers={"Authorization": f"Bearer {cfg.open_router_api_key}"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()["data"]
        return round(float(data["total_credits"]) - float(data["total_usage"]), 4)
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


def create_app(
    graph_factory: Callable[[], Any] = _default_graph,
    balance: Callable[[], Optional[float]] = openrouter_balance,
) -> FastAPI:
    cfg = get_settings()
    state: Dict[str, Any] = {"graph": None, "started": time.monotonic(), "startup_s": None}
    graph_lock = threading.Lock()
    budget_cache: Dict[str, Any] = {"value": None, "at": 0.0}

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
    def quota() -> Dict[str, Any]:
        # Per-visitor limits arrive with budget protection (Phase 7 step 5).
        now = time.monotonic()
        if now - budget_cache["at"] > cfg.api_budget_cache_seconds:
            budget_cache["value"] = balance()
            budget_cache["at"] = now
        remaining = budget_cache["value"]
        return {
            "budget_remaining_usd": remaining,
            "budget_exhausted": remaining is not None and remaining <= 0,
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

    def to_response(final: Dict[str, Any]) -> AskResponse:
        log.info("api.answered", status=final.get("termination_reason"), cached=bool(final.get("cache_hit")))
        return AskResponse(
            answer=final.get("answer") or "",
            status=final.get("termination_reason"),
            cached=bool(final.get("cache_hit")),
            sources=[_source(c, cfg.api_source_excerpt_chars) for c in final.get("chunks") or []],
        )

    @app.post("/api/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> AskResponse:
        question = clean_question(req)
        try:
            with graph_lock, trace_query(question):
                final = state["graph"].invoke({"query": question})
                update_trace_attributes(**trace_attributes(final))
        except Exception as e:
            err = _api_error(e)
            raise HTTPException(err.status, detail=err.detail())
        return to_response(final)

    @app.post("/api/ask/stream")
    def ask_stream(req: AskRequest) -> StreamingResponse:
        question = clean_question(req)  # bad input is a plain 422, before any stream
        events: "queue.Queue[Optional[str]]" = queue.Queue()

        def run() -> None:
            # One worker thread owns the whole run, so the lock and the trace
            # context stay on a single thread while events flow to the client.
            try:
                with graph_lock, trace_query(question):
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
                events.put(sse("done", to_response(final).model_dump()))
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
