import os
import re
from typing import Any, Dict

from dotenv import load_dotenv

from src.config import get_settings
from src.generation.answer_status import check_identifiers, normalize_text, parse_status
from src.obs.logging import get_logger
from src.obs.tracing import make_llm_client

cfg = get_settings()
log = get_logger(__name__)

load_dotenv(dotenv_path=str(cfg.project_root / ".env"))

# Re-read settings after dotenv loads (env vars may have changed)
get_settings.cache_clear()
cfg = get_settings()

# Unified client for Ollama or Remote API, built by the one traced factory
if cfg.use_remote_llm:
    openrouter_key = cfg.open_router_api_key
    openai_key = cfg.openai_api_key
    # OPENAI_BASE_URL is a routing signal: empty means "use the provider default"
    preferred_base_url = os.environ.get("OPENAI_BASE_URL", "")

    if openrouter_key and (not openai_key or "openrouter.ai" in preferred_base_url.lower()):
        api_key = openrouter_key
        base_url = preferred_base_url or cfg.openrouter_base_url
        default_model = cfg.remote_llm_model_openrouter
        LLM_PROVIDER = "openrouter"
    else:
        api_key = openai_key or "dummy"
        base_url = preferred_base_url or cfg.openai_base_url
        default_model = cfg.remote_llm_model_openai
        LLM_PROVIDER = "openai"

    client = make_llm_client(api_key=api_key, base_url=base_url)
    MODEL_NAME = cfg.model_name or default_model
else:
    # Local Ollama endpoint
    client = make_llm_client(
        api_key="ollama",  # required but ignored
        base_url=cfg.ollama_base_url,
    )
    MODEL_NAME = cfg.local_llm_model
    LLM_PROVIDER = "ollama"

# Word-boundary regexes: bare substring matching on "retrieved"/"chunks"
# false-positives on legitimate 3GPP prose (e.g. "the UE retrieved the
# subscription data"). These patterns only catch the system talking about
# its own retrieval mechanism, not the domain's own use of these words.
BANNED_PHRASE_PATTERNS = [
    re.compile(r"\bprovided source\b", re.IGNORECASE),
    re.compile(r"\bprovided chunks?\b", re.IGNORECASE),
    re.compile(r"\bprovided text\b", re.IGNORECASE),
    re.compile(r"\bprovided specifications?\b", re.IGNORECASE),
    re.compile(r"\bsource chunks?\b", re.IGNORECASE),
    re.compile(r"\bretrieved (?:information|context|text|chunks?|documents?)\b", re.IGNORECASE),
    re.compile(r"\bthe chunks?\b", re.IGNORECASE),
]


def _detect_banned_phrase(answer: str) -> str | None:
    for pattern in BANNED_PHRASE_PATTERNS:
        match = pattern.search(answer)
        if match:
            return match.group(0)
    return None


def _format_chunks(chunks) -> str:
    """Chunk block for the generate prompt. Each chunk's text is capped at
    prompt_chunk_char_cap characters (prompt tokens are 66% of measured
    spend); the identifier check reads the same capped text, so it never
    credits the answer with context the model didn't see."""
    cap = get_settings().prompt_chunk_char_cap
    blocks = []
    for c in chunks:
        text = str(c["content"])
        if len(text) > cap:
            text = text[:cap] + " ..."
        blocks.append(f"--- CHUNK {c['clause_id']} (Spec {c['spec_id']}) ---\n{text}")
    return "\n\n".join(blocks)


def _build_generate_messages(query: str, chunks, leak_rephrase: bool = False, generation_terms=None):
    chunk_text = _format_chunks(chunks)

    system_prompt = (
        "You are a 3GPP standards expert. Answer the user's question using only the information in the "
        "source text below.\n\n"
        "Rules:\n"
        "- Be brief: answer in 3-5 sentences or a short list. No introduction, no closing summary, and no "
        "background the question didn't ask for.\n"
        "- Every statement must be supported by the source text. Do not add facts from general knowledge, "
        "even if you believe them to be true.\n"
        "- Use the exact 3GPP terms the source text uses (for example, 5G uses \"registration\" where 4G "
        "uses \"attach\").\n"
        "- Read every chunk before judging how much of the question the source text covers. Text that "
        "answers the question in different words counts: for example, \"X allows the network to select Y\" "
        "answers \"What is the purpose of X?\". If it covers all of the question, just answer. If it covers "
        "only part, answer that part, then say in one sentence which part isn't covered. Only if no chunk "
        "is about the question's subject at all, say so plainly in one sentence and stop.\n"
        "- Say what isn't covered in natural expert language — e.g. \"This detail isn't defined in the 5G "
        "specifications for this procedure\" — never \"the provided chunks don't mention X.\"\n"
        "- Never mention \"chunks,\" \"provided source,\" \"provided text,\" \"provided specifications,\" "
        "\"retrieved information,\" or any variation referring to how you got this information. "
        "The user should never know this is a retrieval system.\n"
        "- Do not use citation brackets like [1].\n"
        "- End with one final line saying how much of the question the source text covers, exactly one "
        "of: \"STATUS: answered\" (all of it), \"STATUS: partial\" (only part), \"STATUS: not_covered\" "
        "(none of it)."
    )

    user_prompt = f"<SOURCE CHUNKS>\n{chunk_text}\n</SOURCE CHUNKS>\n\n<QUERY>\n{query}\n</QUERY>"

    if generation_terms:
        user_prompt += (
            "\n\n<NOTE>\nThis question mixes 4G (EPS) terms ("
            + ", ".join(generation_terms.get("4g", []))
            + ") with 5G terms ("
            + ", ".join(generation_terms.get("5g", []))
            + "). Point out the mismatch and explain how each part works in its own generation. Never "
            "attribute a 4G entity's behaviour to 5G or the reverse.\n</NOTE>"
        )

    if leak_rephrase:
        user_prompt += (
            "\n\n<REPHRASE REQUIRED>\nYour previous answer referred to how this information was obtained "
            "(e.g. mentioning \"chunks\" or \"retrieved\" text). Rephrase the same factual content as confident "
            "expert knowledge, without any reference to sources, retrieval, or documents.\n</REPHRASE REQUIRED>"
        )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


NO_CHUNKS_ANSWER = (
    "The specifications covered here (TS 23.501, TS 24.501, TS 24.301) don't contain enough "
    "relevant detail to answer this question."
)
EMPTY_ANSWER = "No answer could be produced for this question. Please try rephrasing it."


def _complete(messages) -> str:
    kwargs = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": cfg.generate_temperature,
        "max_tokens": cfg.generate_max_tokens,
    }
    if cfg.generate_reasoning_effort and LLM_PROVIDER == "openrouter":
        kwargs["extra_body"] = {"reasoning": {"effort": cfg.generate_reasoning_effort}}
    response = client.chat.completions.create(**kwargs)
    # A reasoning model that spends its whole max_tokens thinking returns
    # content=None; treat that as an empty answer instead of crashing.
    text = response.choices[0].message.content or ""
    # Safety net: strip out any <think> blocks that might leak through
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def generate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """The one LLM call per question: answers from the retrieved chunks and
    labels its own answer answered / partial / not_covered (the STATUS line,
    see src/generation/answer_status.py). Its termination_reason is that
    label, after the identifier check:

    - no chunks retrieved: not_covered, without an LLM call;
    - empty reply (reasoning used the whole token budget): no_answer;
    - missing STATUS line: partial;
    - "answered" but an identifier (T3510, #22, ATTACH REQUEST) is absent
      from the source text: partial, with the identifiers recorded.
    """
    query = state["query"]
    chunks = state.get("chunks") or []
    generation_terms = state.get("generation_terms")

    if not chunks:
        return {"answer": NO_CHUNKS_ANSWER, "termination_reason": "not_covered"}

    messages_payload = _build_generate_messages(query, chunks, generation_terms=generation_terms)
    log.debug("generate_node.payload", messages=messages_payload)
    raw = _complete(messages_payload)

    # Banned-phrase gate: a real gate, not just a log line. One targeted
    # rephrase, then let the leak stand (this node does not loop on itself).
    leaked_phrase = _detect_banned_phrase(raw)
    if leaked_phrase:
        log.warning("generate_node.banned_phrase_leak", phrase=leaked_phrase)
        rephrased = _complete(_build_generate_messages(query, chunks, leak_rephrase=True,
                                                       generation_terms=generation_terms))
        if rephrased and not _detect_banned_phrase(rephrased):
            raw = rephrased
        else:
            log.warning("generate_node.banned_phrase_leak_persisted")

    answer, status = parse_status(normalize_text(raw))
    if not answer:
        log.warning("generate_node.empty_answer")
        return {"answer": EMPTY_ANSWER, "termination_reason": "no_answer"}
    if status is None:
        log.warning("generate_node.missing_status")
        status = "partial"

    result: Dict[str, Any] = {"answer": answer}
    missing = check_identifiers(answer, _format_chunks(chunks))
    if missing:
        result["unsupported_identifiers"] = missing
        if status == "answered":
            log.warning("generate_node.status_downgraded", unsupported_identifiers=missing)
            status = "partial"
    result["termination_reason"] = status
    log.info("generate_node.done", status=status, unsupported_identifiers=missing)
    return result
