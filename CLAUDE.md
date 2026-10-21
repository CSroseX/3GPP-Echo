# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A RAG system that answers 3GPP telecom questions grounded in three specs: TS 23.501 (5G system architecture), TS 24.501 (5G NAS), TS 24.301 (EPS NAS). The three specs were chosen deliberately because they share terminology but differ in procedural detail — cross-spec conflation is the hallucination mode this system is built to defeat.

## Commands

`src/retrieval/retriever.py`, `src/ingestion/indexer.py` and `src/obs/metrics.py` resolve paths against `Settings().project_root` (see `src/config.py`), so they work from any cwd. Other scripts (`src/eval/retrieval_report.py`, `eval/baseline/*`, `eval/run_eval.py`) still use repo-relative paths — run them from the repo root.

```bash
# Qdrant must be live on :6333 for retrieval, the app, and all eval scripts
docker compose up -d qdrant       # Qdrant only (pinned v1.19.2, matches qdrant-client)
docker compose up -d              # + self-hosted Langfuse UI at http://localhost:3000 (optional tracing)

pip install -e ".[ingest,dev]"    # pyproject.toml pins versions; extras: ingest (docling), dev (pytest, ruff), obs (langfuse). requirements.txt is kept but stale

streamlit run app.py              # chat UI + eval dashboard

# Ingestion pipeline — each stage is a separate CLI taking explicit paths.
# Only re-run from the stage you changed; outputs are cached as JSON.
python src/ingestion/parse.py data/raw_pdfs/ts_123501v171100p.pdf data/parsed/ts_123501v171100p.json
python src/ingestion/tree_builder.py data/parsed/ts_123501v171100p.json data/chunks/23.501_tree.json
python src/ingestion/chunker.py data/chunks/23.501_tree.json data/chunks/23.501_chunks.json 23.501 17.11.0
python src/ingestion/indexer.py    # DROPS and recreates the 3gpp_specs collection, then indexes all chunk files
python src/generation/centroids.py # (re)build data/domain_centroids.npz for triage tier 2; also rebuilt automatically when stale

# Single-query end-to-end run through the full graph (verbose)
python src/generation/verify.py "What is the AMF according to TS 23.501?"

# Retrieval only, against four hardcoded sample queries
python src/retrieval/retriever.py

# LLM eval over the golden set — spends real tokens
python -m src.eval.runner [--limit N] [--types normal,adversarial] [--results-path PATH]

# Zero-LLM-token measurement scripts
python -m src.eval.retrieval_report [--output PATH]   # default output overwrites eval/baselines/retrieval_baseline.json
python -m src.eval.triage_sweep                       # writes eval/triage/sweep.json + sweep.svg

# Legacy / frozen
python eval/run_eval.py            # superseded by src.eval.runner; kept as-is
python eval/baseline/preflight.py  # check Qdrant reachability, chunk/point count parity, LLM creds
python eval/baseline/run_baseline.py

# Lint + tests (what CI runs; no network, no Qdrant, no LLM)
ruff check .
pytest tests/ -q
```

`src.eval.runner` writes resumable results to `eval/runner_results.json` (keyed by golden-set `id`) and, for every invocation that executes questions, a run directory `eval/runs/<run_id>/{run.json,per_question.jsonl,summary.json}`. The legacy `eval/run_eval.py` resumes positionally from `eval/results.json` — **delete that file to force a clean legacy run**, otherwise a completed file means zero questions execute. Note that `app.py`'s Eval Dashboard tab still reads `eval/results.json`, not the new runner's outputs (pointing it at `eval/runs/` is issue #27).

Use `retrieval_report --output eval/baselines/ablation_<name>.json` for experiments so the committed baseline isn't overwritten. Retrieval settings can be overridden per run via env vars, since `Settings` is pydantic-settings (e.g. `HYBRID_BM25=false`, `LINEAGE_BOOST=1.0`).

## Architecture

Ingestion writes cached artifacts (JSON, then Qdrant); one LangGraph graph does everything per query — triage, retrieval, sufficiency grading, rewrite, generation, verification. Eval and observability sit around the graph.

**Ingestion (`src/ingestion/`)** — `parse.py` (Docling → `data/parsed/`) → `tree_builder.py` (→ `*_tree.json`) → `chunker.py` (→ `*_chunks.json`) → `indexer.py` (→ Qdrant). The corpus is 4,860 chunks (23.501: 1,220; 24.301: 1,569; 24.501: 2,071); older docs and issues quote 2,644, which is stale.

- `tree_builder.py` rebuilds document hierarchy from Docling's flat block list using a **depth stack**: clause depth = dot count (`5.3.4` → 3); on a new heading, pop until the stack top has strictly smaller depth, leaving the true parent on top. This produces each clause's full `lineage`. The heading regex must tolerate letter-suffixed clause IDs (`4.2.5a`, `4.2.8.1A`) — an earlier numeric-only regex silently buried 37 real clauses. If you touch that regex, inspect what lands in the downgraded (non-clause text) pile rather than trusting the summary count.
- `chunker.py` uses a `len//4` token heuristic with soft limit 400 / hard cap 800 (`chunk_soft_limit` / `chunk_hard_cap` in config). **Tables are never split or flattened** — a table emits one chunk whose `content` is the raw 2D `grid`, and encountering one flushes the pending text buffer to preserve reading order.
- `indexer.py` prepends a lineage header (`Spec {spec_id} {version} Clause {clause_id} {clause_title}`) to every chunk before embedding, and stores the **entire chunk dict as the Qdrant payload** — so retrieval filters and the generator prompt both read metadata straight off the payload. Tables go through `format_table_for_embedding` (markdown-ish) for the vector only; the payload keeps the grid. Vectors are 384-dim (`BAAI/bge-small-en-v1.5` via FastEmbed, cosine, configured in `src/config.py`) — changing the embed model means changing `vector_size` and reindexing.
- `src/ingestion/chunk_ids.py` (`assign_chunk_ids`) computes a deterministic `chunk_id = sha1(spec_id|clause_id|ordinal)`, where `ordinal` is the chunk's position among chunks sharing the same `(spec_id, clause_id)` — `clause_id` alone isn't unique (every frontmatter chunk shares `clause_id "0"`). It is shared by the indexer (Qdrant point ids and payload `chunk_id`) and the retriever's BM25 index; both load chunk files in **sorted order**, which is what makes the ids agree. Re-indexing unchanged chunk files reproduces identical ids and point counts.

**Retrieval (`src/retrieval/`)** — one `Retriever` class in `retriever.py`, dual-path, hybrid, reranked:

- `_parse_query` regex-detects a spec number (`23.501`, optionally `TS`-prefixed) and/or a clause reference (`clause|sec|section|subclause 5.5.1`).
- Targeted path builds a Qdrant payload `Filter`. Clause filtering is **prefix-expanded**: a hit on `5.5` matches `5.5` plus every descendant, resolved against `valid_clause_ids` loaded from the chunk JSON files at construction time. This is why the retriever needs `data/chunks/` on disk even though vectors live in Qdrant.
- `search(query, top_k, candidate_k)` reranks `candidate_k` candidates, defaulting to `rerank_multiplier * top_k` (default 8 → 40 at `top_k=5`). This replaced the old degenerate `max(fetch_k=20, top_k)` (#35).
- **Hybrid** (`hybrid.py`, `hybrid_bm25=True` by default, #36): an in-process `rank-bm25` index over all chunks, honouring the same spec/clause targeting, fused with the dense Qdrant ranking via Reciprocal Rank Fusion (`rrf_k=60`), keyed by `chunk_id`. BM25-only hits have `qdrant_score: None`.
- Fused candidates are reranked with `cross-encoder/ms-marco-MiniLM-L-6-v2`. Each result carries `qdrant_score`, `bm25_score`, `cross_score` (raw logit), `lineage_match`, and final `score = cross_score + lineage_boost * lineage_match`.
- **Lineage boost** (`lineage.py`, #38) scores how fully the query names a chunk's clause title or an ancestor's. `lineage_boost` defaults to **0.0 (off)** because it also fully matches cross-spec decoys (e.g. 24.301 "GUTI" for a 5G-GUTI question); a value must be picked by sweeping it with `retrieval_report`.
- Construction loads two models and builds the BM25 index — it is slow. `app.py` caches the `Retriever` and compiled graph with `@st.cache_resource`; the eval runner and `verify.py` construct one and pass it to `build_graph(retriever=...)`.

**Generation (`src/generation/`)** — LangGraph state machine in `graph.py`. Retrieval is a node inside the graph (callers no longer call `retriever.search()` before invoking it):

```
START → triage ──out_of_domain──→ refuse → END
          │ in_domain (or fail-open)
          ↓
       retrieve → grade_sufficiency ──insufficient, rewrites left──→ rewrite_query → retrieve
                        │            ──insufficient, exhausted───→ abstain → END   (no-op rewrite → abstain)
                        │ sufficient
                        ↓
                    generate → verify ──passed──→ END
                                  │ failed, retries left → generate
                                  │ failed, exhausted / verifier down → abstain → END
```

Every conditional edge is a pure function in `src/generation/routers.py` (`after_triage`, `after_grade`, `after_rewrite`, `should_retry`), unit-tested without a graph or LLM. `should_retry`'s `"flag_unverified"` return value is a legacy routing-key name that `graph.py` wires to `abstain`. `termination_reason` ends as one of `verified | verification_failed | insufficient_context | out_of_domain | verifier_unavailable` (`TERMINATION_REASONS` in `state.py`). `GraphState` (`state.py`) carries the core fields (`query, chunks, answer, verification_passed, feedback, retries`), the Phase 2 counters (`attempt, grounding_retries, transport_attempts, termination_reason, abstention`) and the Phase 4 decision fields (`triage_*`, `retrieval_queries`, `rewrites`, `rewrite_noop`, `n_relevant_chunks`, `relevance_flags`, `top1_cross_score`, `sufficiency_signal`); `citations` is still an unpopulated placeholder.

- `src/generation/nodes/` is a package: `core.py` (`generate_node`, `verify_claims_node`, LLM client setup), `abstain.py`, `triage.py` (`make_triage_node`, `refuse_node`), `retrieve.py` (`make_retrieve_node`), `grade.py` (`make_grade_sufficiency_node`), `rewrite.py` (`rewrite_query_node`), and `llm.py` (the small `chat_completion` seam the decision nodes call). `__init__.py` re-exports these plus `client`/`MODEL_NAME`, so `from src.generation import nodes as gen_nodes; gen_nodes.client` still works and tests that monkeypatch it intercept every LLM call. The `make_*` factories take injected `embed`/`llm`/`retriever_factory` callables — test seams, also exposed on `build_graph()`.
- **triage** (#30) routes `retrieve | refuse` in three tiers, cheapest first: (1) lexical — spec id, existing clause ref, corpus acronym/long form, or clause-title bigram, from the corpus-derived lexicon in `lexicon.py` (no hand-written keyword list; tier 1 only ever accepts); (2) embedding — max cosine against per-spec clause centroids (`centroids.py`, cached to `data/domain_centroids.npz`, stamped with model + chunk-file fingerprint and rebuilt when stale), using the retriever's already-loaded BGE model: `< triage_refuse_below` refuses, `>= triage_accept_above` accepts; (3) one LLM yes/no capped at `triage_llm_max_tokens`, only for the band in between. **Fail-open**: if centroids or the LLM are unavailable, the question goes to retrieve. The two thresholds (0.60 / 0.72) are **provisional** until `python -m src.eval.triage_sweep` is run with the BGE model. `refuse_node` is a fixed refusal with no LLM call.
- **retrieve** searches `default_top_k` chunks for `query`, or for each query in `retrieval_queries` after a rewrite, round-robin merging and deduplicating split queries.
- **grade_sufficiency** (#31) decides whether the context can answer at all: if the top-1 cross-encoder score is below `sufficiency_min_top1_score`, no LLM call is made; otherwise one binary per-chunk relevance call over the top `sufficiency_top_n`, falling back to a cross-encoder score threshold if that call fails. `after_grade` routes on `n_relevant_chunks >= sufficiency_min_relevant`. When sufficient, only relevant chunks are passed on (`sufficiency_filter_chunks`).
- **rewrite_query** (#32) is deterministic, not an LLM paraphrase: strip conversational framing, expand acronyms both ways from the lexicon, and split a mixed 4G/5G question into a 4G part pinned to 24.301 and a 5G part. Capped at `max_rewrites` (1); past the cap, or if the rewrite reproduces queries already tried, it sets `rewrite_noop` and the graph abstains.
- `generate_node` owns the `attempt` counter (increments itself); a first-pass success records `attempt == 1`. The legacy `retries` field is still populated (mirrors `grounding_retries`) because `app.py` and the eval scripts read it. Chunk text injected into generate/verify prompts is capped at `prompt_chunk_char_cap` per chunk.
- `verify_claims_node` is a strict-entailment judge returning JSON (`is_supported`, `reasoning`, `unsupported_claims`) at temperature 0, with a **typed exception boundary**: `APIStatusError` / `APIConnectionError` / `APITimeoutError` are transport failures — they set `termination_reason = "verifier_unavailable"`, bump `transport_attempts`, and do **not** increment `grounding_retries` or inject feedback. Malformed JSON gets one reask, then is treated as transport. Only a valid JSON response with `is_supported: false` increments `grounding_retries`.
- Unsupported claims are fed back as `feedback` into the next `generate` call. The router sends `verifier_unavailable` straight to `abstain` and otherwise allows up to `max_retries` grounding retries. `abstain_node` returns a **structured abstention** (`found_clauses`, `unsupported_claims` parsed out of `feedback`, `termination_reason`) and preserves an upstream `termination_reason` (`verifier_unavailable`, `insufficient_context`) rather than overwriting it. `app.py`'s `render_assistant_message()` badges every terminal state and shows `unsupported_claims` in an expander.
- The generate prompt deliberately hides the retrieval system from the user: a word-boundary banned-phrase gate (`_detect_banned_phrase` in `nodes/core.py`) is a **real gate** — one targeted rephrase attempt, then the leak is allowed to stand. Bare substring matching on "retrieved"/"chunks" was replaced because it false-positived on legitimate 3GPP prose. `<think>` blocks are stripped with regex.
- LLM client selection lives in `nodes/core.py`, read from `.env` at import: `USE_REMOTE_LLM=false` pins a local Ollama endpoint (`localhost:11434`, `qwen3.5:4b`); true picks OpenRouter when `OPEN_ROUTER_API_KEY` is set (or the base URL mentions openrouter), else OpenAI-compatible with `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `MODEL_NAME`. The client itself comes from `make_llm_client()` in `src/obs/tracing.py`. Every node shares one client and model.

**Observability (`src/obs/`)**

- `logging.py` — `get_logger()` (structlog): JSON lines to `logs/app.jsonl`, pretty console in dev.
- `tracing.py` — tracing is **optional and non-fatal**. With `LANGFUSE_HOST` unset (or `langfuse` not installed), `make_llm_client()` returns a plain `openai.OpenAI` client and tracing helpers are no-ops. With it set (values in `.env.example` match the docker-compose Langfuse), the client is Langfuse-traced. `graph.py` wraps every node in `traced_node()` (one span per node); callers wrap a query in `trace_query()` and attach `trace_attributes(final_state)` so a query is one trace. Independently of Langfuse, every client records each response's token usage to a process-wide log (`usage_snapshot()` / `usage_since()`).
- `metrics.py` — `RunRecorder`, **wired into `src/eval/runner.py`**: per-node latency, node path, tokens (from the usage log, so no Langfuse dependency) and cost estimates (static price table in config, labelled ESTIMATE) per question, written to `eval/runs/<run_id>/`. Not wired into `app.py`.

**Eval (`eval/`, `src/eval/`)** — `eval/golden/golden_set.v1.json` is the canonical, versioned set (18 questions; stable `id`, `type` of `normal | out_of_scope | adversarial`, `gold_clauses`, `retrieval_scored`, `corpus_answerable`, `borderline`), merged from `eval/eval_set.json` and `eval/baseline/gold.json`. Version it (v2) rather than editing v1 in place. `tests/test_golden_set.py` asserts every `gold_clauses` entry resolves to a real chunk (exact or descendant). `eval/baseline/` is the frozen "before" measurement — its scripts write only inside `eval/baseline/` and shouldn't be changed.

- `src/eval/metrics.py` scores strict and **prefix-credit** matching side by side (a retrieved clause counts if it's the gold clause or a strict descendant — some gold clauses, e.g. `24.501/5.1.3.2`, `23.501/5.15.2`, exist only as descendant chunks), plus nDCG@10 (each gold clause credited once).
- `src/eval/runner.py` supersedes `eval/run_eval.py`: resume keyed by golden-set `id`, refused (`GoldenSetDriftError`) if the golden set's content hash changed; corrupt results raise `ResultsFileCorruptError`; writes are atomic (temp file + `os.replace`); `--limit`/`--types` for cheap iteration; records a `RunRecorder` run.
- The "conflation catch rate" metric (`adv_caught = retries > 0`, in `runner.py`, `run_eval.py` and `app.py`) measures verifier dissatisfaction, not conflation detection. It is known to be meaningless and is slated for replacement (#41) — don't report it as a real metric.
- `src/eval/retrieval_report.py` — zero-LLM-token retrieval scorer: runs `Retriever.search()` against live Qdrant for every `retrieval_scored` question and writes strict + prefix-credit recall@5/@20, MRR, nDCG@10 and p50/p95 latency. Re-run it whenever retrieval, chunking or the golden set changes.
- `src/eval/triage_sweep.py` — zero-LLM-token sweep of triage tier-2 thresholds against the golden set; writes `eval/triage/sweep.json` and `sweep.svg` with recommended `triage_refuse_below` / `triage_accept_above`. Needs the BGE model.

**CI (`.github/workflows/ci.yml`)** — one job on push to `main` and on PRs: `ruff check .` then `pytest tests/ -q` with `USE_REMOTE_LLM=false`. No network, Qdrant or LLM; tests use fakes injected through the node factories and `build_graph()` seams (`tests/test_graph_topology.py` drives the whole compiled graph this way).

## Conventions

- Entry-point scripts append the project root to `sys.path` before importing `src.*`; keep that in any new script.
- Use `get_logger()` from `src/obs/logging.py` instead of `print()` for debug output, payload dumps, and warnings/errors. CLI entry points (`retriever.py`'s `__main__` block, eval reports, missing-dependency messages) still use plain `print()` since that output is the point of running the script.
- Every tunable literal lives in `src/config.py` (`get_settings()`, cached); any field can be overridden by an env var of the same name.
- `spec_id` is bare and dotted (`23.501`, no `TS`); `version` is a separate field (`17.11.0`). Both are passed as chunker CLI args, so a wrong invocation mislabels every chunk from that spec.
- Several files wrap `sys.stdout` in a UTF-8 `TextIOWrapper` — Windows console default encoding breaks on spec text.
- Domain knowledge used at runtime (lexicon, centroids) is **derived from `data/chunks/`**, never hand-written lists.
- Anything that spends real LLM tokens (`src.eval.runner`, `eval/run_eval.py`, `verify.py`, the app) needs an explicit go-ahead before running; prefer `--limit`/`--types` when iterating.

## Planned work (to-dos)

The full production-hardening plan lives in [docs/production-hardening-plan.md](docs/production-hardening-plan.md) — read it before starting any phase. It carries the measured baseline, the defect diagnoses, and the per-phase verification steps.

Measured starting state (frozen in `eval/baseline/`, 18 questions): 1/18 grounded on first pass, 0/6 out-of-scope refusals, 124,701 tokens per run, of which 46,452 (37%) are spent answering questions that should have been refused. Progress is tracked via GitHub issues on `CSroseX/Mavenir-Assignment` (one epic per phase, one sub-issue per item). **The tracker may lag the code** — issues are often left open after code merges because a checklist item needs a measurement run; verify against the code and the issue's comments before trusting its state.

Many open items below are blocked on **measurement runs, not code**. Two kinds: zero-LLM-token runs (`retrieval_report`, `triage_sweep`) need only Qdrant plus the locally cached models; the LLM eval run (#21) spends real tokens and needs an explicit go-ahead.

- [x] **Phase 1 — Foundations.** Done: config module (#2), golden set v1 (#3), `@st.cache_resource` (#4), structlog (#5), pinned `pyproject.toml` (#6), prefix-credit scorer + nDCG@10 (#7), golden-set contract test (#8), anchored chunk glob (#9), deterministic `chunk_id` (#10), CI job 1 (#11), committed `eval/baselines/retrieval_baseline.json`.
- [ ] **Phase 2 — Reliability and truthful state (#12).** All code done (#13–#20). Open: #21 — one clean full 18-question run with `src.eval.runner` (spends tokens; needs go-ahead).
- [ ] **Phase 3 — Observability (#22).** Done: traced client factory (#24), per-node spans and one trace per query (#25), `RunRecorder` (#26), since wired into the runner. Open: #23 — `docker-compose.yml` is merged and Qdrant was verified healthy, but the Langfuse services have never been brought up; #27 — Trace tab in `app.py`, and point the dashboard at `eval/runs/`.
- [ ] **Phase 4 — Decision-nodes (#28).** All nodes and the topology are merged (#29–#33). Open checklist items: #30 — run `triage_sweep` to replace the provisional thresholds, and confirm 6/6 refusals (excluding borderline Q15) on a real-model run; #33 — the tokens-per-run drop from 124,701 and a committed `eval/runs/` full run. Both wait on #21.
- [ ] **Phase 5 — Retrieval quality and judge validation (#34).** Code merged: `rerank_multiplier` (#35), BM25 + RRF (#36), lineage boost (#38, off by default). Each still needs its metric delta from `retrieval_report --output eval/baselines/ablation_<name>.json`; #38 also needs a `lineage_boost` value picked by sweeping it, and #36's sparse-vector future-work note belongs in the README (#45). Not started: reranker A/B (#37), label the 6 adversarial questions + cross-spec coverage (#39), Cohen's κ judge validation (#40), real conflation metric (#41), CI retrieval-regression ratchet with Qdrant snapshots (#42).
- [ ] **Phase 6 — Polish (#43).** Nightly / `workflow_dispatch` LLM eval job (#44); README with before/after and ablation tables (#45). This file was updated for #46.
