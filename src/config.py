"""Central configuration for the 3GPP RAG system, powered by pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root() -> Path:
    """Walk up from this file to find the directory containing 'src/'."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "src").is_dir() and (current / "data").is_dir():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Infrastructure ──────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "3gpp_specs"

    ollama_base_url: str = "http://localhost:11434/v1"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openai_base_url: str = "https://api.openai.com/v1"

    # ── Models ──────────────────────────────────────────────────────
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    # Outputs raw logits on a range similar to MiniLM's, so lineage_boost
    # keeps its meaning. A sigmoid-output reranker (bge-reranker-*) would
    # need the boost re-tuned. Comparison: DECISIONS.md, 2026-10-24.
    reranker_model: str = "cross-encoder/ettin-reranker-32m-v1"
    # Tokens of (query + chunk) the reranker reads. Ettin accepts 8K, but
    # unsplit table chunks run to ~10K tokens and made split-query searches
    # take 20-35 s; 512 is MiniLM's limit, i.e. what we measured before.
    reranker_max_length: int = 512
    local_llm_model: str = "qwen3.5:4b"
    remote_llm_model_openrouter: str = "openai/gpt-oss-20b"
    remote_llm_model_openai: str = "gpt-3.5-turbo"

    # ── Vector DB ───────────────────────────────────────────────────
    vector_size: int = 384

    # ── Retrieval ───────────────────────────────────────────────────
    default_top_k: int = 5
    # Candidates sent to the cross-encoder = rerank_multiplier * top_k.
    # (Was a flat fetch_k=20 behind max(fetch_k, top_k), so top_k=5 and
    # top_k=20 both reranked the same 20 candidates.)
    # 4 (= 20 candidates at top_k=5) measured as good as 8 at half the
    # latency; see DECISIONS.md and eval/baselines/ablation_*.json.
    rerank_multiplier: int = 4
    # BM25 (in-process, src/retrieval/hybrid.py) fused with dense via RRF.
    # Off: with the current cross-encoder it lowered recall@5 (0.67 -> 0.50).
    hybrid_bm25: bool = False
    rrf_k: int = 60
    # Added to the cross-encoder logit × lineage_match (src/retrieval/lineage.py).
    # 2.0 measured best (prefix recall@5 0.67 -> 0.75); it can also match
    # decoys (24.301 "GUTI" for a 5G-GUTI question), which the sweep didn't hit.
    lineage_boost: float = 2.0

    # ── Generation ──────────────────────────────────────────────────
    # 0: the same chunks should give the same answer (at 0.3 Q6 flipped between
    # answered and not_covered across runs on identical context).
    generate_temperature: float = 0.0
    # Safety net on answer length; the prompt asks for brevity. For a
    # reasoning model (gpt-oss-20b) the cap also covers its hidden thinking,
    # so too low a cap returns an empty answer: at 1000, 3 of 14 benchmark
    # questions came back empty once the prompt asked it to read every chunk,
    # and at 2000, 2 of 29 in the full v2 run (both hit exactly 2000).
    generate_max_tokens: int = 5000
    # "low" | "medium" | "high": how long a reasoning model thinks before
    # answering (OpenRouter's `reasoning.effort`; other providers don't get
    # it). Empty = the model's own default (medium for gpt-oss-20b). "low"
    # since 2026-10-25, together with the 5000 cap, against empty answers.
    generate_reasoning_effort: str = "low"

    # ── Chunking ────────────────────────────────────────────────────
    chunk_soft_limit: int = 400
    chunk_hard_cap: int = 800

    # ── Indexing ────────────────────────────────────────────────────
    indexer_batch_size: int = 100

    # ── Eval ────────────────────────────────────────────────────────
    eval_sleep_seconds: int = 5
    # Ranked-list length the retrieval report scores (recall@20 needs 20).
    eval_top_k: int = 20

    # ── Cost estimation (USD per 1k tokens, clearly an ESTIMATE) ───
    cost_per_1k_input_tokens: float = 0.0015
    cost_per_1k_output_tokens: float = 0.002

    # ── LLM selection (from .env) ───────────────────────────────────
    use_remote_llm: bool = False
    open_router_api_key: str = ""
    openai_api_key: str = ""
    model_name: str = ""

    # ── Phase 4 decision-node settings ──────────────────────────────
    # Corpus lexicon (src/generation/lexicon.py): an acronym-shaped token
    # must occur at least this often in spec text to count as a domain term
    # (keeps one-off mentions like XML/HTTP out of the lexicon).
    lexicon_min_term_freq: int = 10

    # rewrite_query (used by triage to split 4G/5G-mixed questions).
    # Generation affinity: an acronym is 4G- or 5G-affine when its per-token
    # rate in one spec group is >= this ratio times its rate in the other.
    rewrite_generation_affinity_ratio: float = 3.0
    # Two-word phrases ("attach request", "tracking area") get an affinity
    # too, with a stricter ratio and a minimum count, since ordinary prose
    # bigrams outnumber acronyms by far.
    rewrite_phrase_affinity_ratio: float = 10.0
    rewrite_phrase_min_freq: int = 20
    rewrite_4g_spec_ids: list[str] = ["24.301"]
    rewrite_5g_spec_ids: list[str] = ["23.501", "24.501"]

    # Answer cache (src/generation/answer_cache.py): a question is a cache
    # hit if its normalized text matches, or if it is at least this cosine-
    # similar to a stored question AND mentions the same 3GPP terms.
    answer_cache_path: str = "data/answer_cache.sqlite"
    answer_cache_similarity: float = 0.95

    # triage_node. Tier 2 compares the query's max cosine against per-spec
    # clause centroids (one per clause prefix at this depth, cached to the
    # .npz below): < refuse_below -> refuse, >= accept_above -> retrieve,
    # in between -> one tier-3 LLM yes/no capped at triage_llm_max_tokens.
    # The two thresholds come from src/eval/triage_sweep.py run against the
    # BGE model (eval/triage/sweep.json); sweep_margin pads the golden-set
    # extremes it derives them from.
    triage_centroids_path: str = "data/domain_centroids.npz"
    triage_centroid_clause_depth: int = 2
    triage_centroid_exclude_clauses: list[str] = ["0", "2"]  # frontmatter, References
    triage_refuse_below: float = 0.595
    triage_accept_above: float = 0.7197
    triage_llm_max_tokens: int = 10
    triage_sweep_margin: float = 0.02

    # Per-chunk character cap on chunk text injected into the generate
    # prompt (prompt tokens are 66% of measured spend).
    prompt_chunk_char_cap: int = 2400

    @property
    def project_root(self) -> Path:
        return _find_project_root()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
