# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A RAG system that answers 3GPP telecom questions grounded in three specs: TS 23.501 (5G system architecture), TS 24.501 (5G NAS), TS 24.301 (EPS NAS). The three specs were chosen deliberately because they share terminology but differ in procedural detail — cross-spec conflation is the hallucination mode this system is built to defeat.

## Commands

`src/retrieval/retriever.py`, `src/ingestion/indexer.py` and `src/obs/metrics.py` resolve paths against `Settings().project_root` (see `src/config.py`), so they work from any cwd. Other scripts (`src/eval/retrieval_report.py`, `eval/baseline/*`, `eval/run_eval.py`) still use repo-relative paths — run them from the repo root.

```bash
# Qdrant must be live on :6333 for retrieval, the app, and all eval scripts
docker compose up -d qdrant       # Qdrant only (pinned v1.19.2, matches qdrant-client); data persists in volume 3gpp-echo_qdrant_data
docker compose up -d              # + self-hosted Langfuse UI at http://localhost:3000 (optional tracing)

pip install -e ".[ingest,dev]"    # pyproject.toml pins versions; extras: ingest (docling), dev (pytest, ruff), obs (langfuse), deploy (modal). requirements.txt is kept but stale

streamlit run app.py              # chat UI + eval dashboard (being replaced by the API below + SvelteKit, #59)
uvicorn src.api.main:app --port 8000   # public HTTP API: POST /api/ask, POST /api/ask/stream (SSE), GET /api/quota, GET /api/health

# Frontend (frontend/, SvelteKit 3 + Svelte 5, static build). Talks to VITE_API_BASE (default http://localhost:8000)
cd frontend && npm install && npm run dev     # http://localhost:5173, live reload
npm run build                                 # static site in frontend/build (Cloudflare Pages)
npx svelte-check --tsconfig ./tsconfig.json   # type check
npm run record                                # record example runs for free replay — spends LLM tokens, needs go-ahead

# Deploy (Phase 7) — reads .env; QDRANT_CLOUD_URL / QDRANT_CLOUD_API_KEY are kept separate from
# QDRANT_URL so local runs stay on local Qdrant
python deploy/copy_qdrant.py      # copy points + vectors from local Qdrant to Qdrant Cloud (adds the keyword indexes Cloud needs for spec_id/clause_id filters)
python deploy/modal_app.py        # build the Dockerfile on Modal, update the named secret, deploy, zero-token smoke check
docker build -t 3gpp-echo-api .   # same image, runnable anywhere (port 7860, config only via env vars)

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

# LLM eval over the golden set — spends real tokens (1 LLM call per in-domain question)
python -m src.eval.runner --golden eval/golden/golden_set.v2.json [--ids 1,2,3] [--types normal,adversarial] \
    [--max-llm-calls N] [--results-path PATH]

# Zero-LLM-token measurement scripts
python -m src.eval.retrieval_report --pipeline --golden eval/golden/golden_set.v2.json \
    --grades eval/pooling/v2/grades.json --output eval/baselines/v2_<name>.json
    # --pipeline searches the way the app does (triage's 4G/5G split first); --grades adds
    # chunk-level scoring (answer chunk in top 5/10) against the pooled answer key.
    # Without --output it overwrites eval/baselines/retrieval_baseline.json (v1).
python -m src.eval.pool_candidates --out-dir eval/pooling/<name>   # pool candidates from 7 search methods for grading
python -m src.eval.triage_sweep                       # writes eval/triage/sweep.json + sweep.svg

# Legacy / frozen
python eval/run_eval.py            # superseded by src.eval.runner; kept as-is
python eval/baseline/preflight.py  # check Qdrant reachability, chunk/point count parity, LLM creds
python eval/baseline/run_baseline.py

# Lint + tests (what CI runs; no network, no Qdrant, no LLM)
ruff check .
pytest tests/ -q
pytest tests/test_api.py -q -k quota   # single file / single test
```

`src.eval.runner` writes resumable results to `eval/runner_results.json` (keyed by golden-set `id`) and, for every invocation that executes questions, a run directory `eval/runs/<run_id>/{run.json,per_question.jsonl,summary.json}`. The legacy `eval/run_eval.py` resumes positionally from `eval/results.json` — **delete that file to force a clean legacy run**, otherwise a completed file means zero questions execute. Note that `app.py`'s Eval Dashboard tab still reads `eval/results.json`, not the new runner's outputs (pointing it at `eval/runs/` is issue #27).

Use `retrieval_report --output eval/baselines/v2_<name>.json` for experiments so the committed baseline isn't overwritten. The current retrieval baseline is `eval/baselines/v2_pipeline_default.json` (answer chunk in top 5: 20/29). Chunks a new setup surfaces that the answer key never graded show up as `unjudged_in_top_5`; grade them into an `eval/pooling/v2/supplement_*.jsonl` (merged automatically) before trusting a score. Retrieval settings can be overridden per run via env vars, since `Settings` is pydantic-settings (e.g. `HYBRID_BM25=false`, `LINEAGE_BOOST=1.0`).

## Architecture

Ingestion writes cached artifacts (JSON, then Qdrant); one LangGraph graph does everything per query — input guardrail (answer cache + triage), retrieval, and one generation call that labels its own answer. Eval and observability sit around the graph.

**Ingestion (`src/ingestion/`)** — `parse.py` (Docling → `data/parsed/`) → `tree_builder.py` (→ `*_tree.json`) → `chunker.py` (→ `*_chunks.json`) → `indexer.py` (→ Qdrant). The corpus is 6,124 chunks (23.501: 1,568; 24.301: 1,831; 24.501: 2,725); older docs and issues quote 4,860 or 2,644, both from before bulleted lists were indexed.

- `tree_builder.py` rebuilds document hierarchy from Docling's flat block list using a **depth stack**: clause depth = dot count (`5.3.4` → 3); on a new heading, pop until the stack top has strictly smaller depth, leaving the true parent on top. This produces each clause's full `lineage`. The heading regex must tolerate letter-suffixed clause IDs (`4.2.5a`, `4.2.8.1A`) — an earlier numeric-only regex silently buried 37 real clauses. If you touch that regex, inspect what lands in the downgraded (non-clause text) pile rather than trusting the summary count. Docling stores bulleted lists as `groups`; `iter_reading_order` expands them (recursively, in reading order) — before that fix about 37% of the spec text was silently dropped. IE-diagram bit rows ("8 7 6 5 4 3 2 1") labelled `section_header` are kept as text, not parsed as clause "8".
- `chunker.py` uses a `len//4` token heuristic with soft limit 400 / hard cap 800 (`chunk_soft_limit` / `chunk_hard_cap` in config). **Tables are never split or flattened** — a table emits one chunk whose `content` is the raw 2D `grid`, and encountering one flushes the pending text buffer to preserve reading order.
- `indexer.py` prepends a lineage header (`Spec {spec_id} {version} Clause {clause_id} {clause_title}`) to every chunk before embedding, and stores the **entire chunk dict as the Qdrant payload** — so retrieval filters and the generator prompt both read metadata straight off the payload. Tables go through `format_table_for_embedding` (markdown-ish) for the vector only; the payload keeps the grid. Vectors are 384-dim (`BAAI/bge-small-en-v1.5` via FastEmbed, cosine, configured in `src/config.py`) — changing the embed model means changing `vector_size` and reindexing.
- `src/ingestion/chunk_ids.py` (`assign_chunk_ids`) computes a deterministic `chunk_id = sha1(spec_id|clause_id|ordinal)`, where `ordinal` is the chunk's position among chunks sharing the same `(spec_id, clause_id)` — `clause_id` alone isn't unique (every frontmatter chunk shares `clause_id "0"`). It is shared by the indexer (Qdrant point ids and payload `chunk_id`) and the retriever's BM25 index; both load chunk files in **sorted order**, which is what makes the ids agree. Re-indexing unchanged chunk files reproduces identical ids and point counts.

**Retrieval (`src/retrieval/`)** — one `Retriever` class in `retriever.py`, dual-path, hybrid, reranked:

- `_parse_query` regex-detects a spec number (`23.501`, optionally `TS`-prefixed) and/or a clause reference (`clause|sec|section|subclause 5.5.1`).
- Targeted path builds a Qdrant payload `Filter`. Clause filtering is **prefix-expanded**: a hit on `5.5` matches `5.5` plus every descendant, resolved against `valid_clause_ids` loaded from the chunk JSON files at construction time. This is why the retriever needs `data/chunks/` on disk even though vectors live in Qdrant.
- `search(query, top_k, candidate_k)` reranks `candidate_k` candidates, defaulting to `rerank_multiplier * top_k` (default 4 → 20 at `top_k=5`; 8 → 40 measured no better at twice the latency). This replaced the old degenerate `max(fetch_k=20, top_k)` (#35). Measured defaults and their evidence are logged in `DECISIONS.md`.
- **Hybrid** (`hybrid.py`, #36; `hybrid_bm25=False` by default — with the current cross-encoder it lowered prefix recall@5 from 0.67 to 0.50): an in-process `rank-bm25` index over all chunks, honouring the same spec/clause targeting, fused with the dense Qdrant ranking via Reciprocal Rank Fusion (`rrf_k=60`), keyed by `chunk_id`. BM25-only hits have `qdrant_score: None`.
- Fused candidates are reranked with `cross-encoder/ettin-reranker-32m-v1` (replaced `ms-marco-MiniLM-L-6-v2` on 2026-10-24; answer chunk in top 5 on golden set v2: 17/29 → 20/29). Each result carries `qdrant_score`, `bm25_score`, `cross_score` (raw logit), `lineage_match`, and final `score = cross_score + lineage_boost * lineage_match`.
- **Lineage boost** (`lineage.py`, #38) scores how fully the query names a chunk's clause title or an ancestor's. `lineage_boost` defaults to **2.0**, picked by sweeping it with `retrieval_report` (prefix recall@5 0.67 → 0.75 with BM25 off). It can also match cross-spec decoys (e.g. 24.301 "GUTI" for a 5G-GUTI question), which the 6-question sweep didn't hit.
- Construction loads two models and builds the BM25 index — it is slow. `app.py` caches the `Retriever` and compiled graph with `@st.cache_resource`; the eval runner and `verify.py` construct one and pass it to `build_graph(retriever=...)`.

**Generation (`src/generation/`)** — LangGraph state machine in `graph.py`. Retrieval is a node inside the graph (callers no longer call `retriever.search()` before invoking it):

```
START → cache_lookup ──hit──→ END                     (cached "answered" answer reused, zero LLM calls)
            │ miss
            ↓
          triage ──out_of_domain──→ refuse → END
            │ in_domain (4G/5G-mixed questions get one retrieval query per generation)
            ↓
          retrieve → generate → cache_store → END        (one LLM call per answered question)
```

The conditional edges are pure functions in `src/generation/routers.py` (`after_cache`, `after_triage`), unit-tested without a graph or LLM. `termination_reason` ends as one of `answered | partial | not_covered | no_answer | out_of_domain` (`TERMINATION_REASONS` in `state.py`). There is **no verifier** (removed 2026-10-25): it was a second LLM call over the same chunks, retries reused the same chunks, and on the 4G/5G traps it rejected correct answers. `GraphState` (`state.py`) carries `query, chunks, answer, termination_reason, unsupported_identifiers` and the guardrail fields (`cache_hit`, `triage_*`, `mixed_generation`, `generation_terms`, `retrieval_queries`); `citations` is still an unpopulated placeholder.

- `src/generation/nodes/` is a package: `core.py` (`generate_node`, LLM client setup), `triage.py` (`make_triage_node`, `refuse_node`), `retrieve.py` (`make_retrieve_node`), `guardrail.py` (`make_cache_lookup_node`, `make_cache_store_node`), `rewrite.py` (`rewrite_query`, used by triage), and `llm.py` (the small `chat_completion` seam triage's LLM tier calls; it can request a lower reasoning effort, sent to OpenRouter only). `__init__.py` re-exports these plus `client`/`MODEL_NAME`, so `from src.generation import nodes as gen_nodes; gen_nodes.client` still works and tests that monkeypatch it intercept every LLM call. The `make_*` factories take injected `embed`/`llm`/`retriever_factory` callables — test seams, also exposed on `build_graph()`.
- **Input guardrail** = `cache_lookup` + triage. The answer cache (`src/generation/answer_cache.py`, SQLite at `answer_cache_path`) stores only answers labelled `answered`. A question hits on normalized text (case, punctuation, spacing ignored), or on embedding cosine ≥ `answer_cache_similarity` (0.95) **and** the same set of 3GPP terms (corpus acronyms + spec numbers), so "What timer does the AMF use…" never returns a cached MME answer. `build_graph(answer_cache=None)` disables it: `app.py` passes a cache, the eval runner never does, so benchmarks always exercise the full pipeline.
- **triage** (#30) routes `retrieve | refuse` in three tiers, cheapest first: (1) lexical — spec id, existing clause ref, corpus acronym/long form, or clause-title bigram, from the corpus-derived lexicon in `lexicon.py` (no hand-written keyword list; tier 1 only ever accepts); (2) embedding — max cosine against per-spec clause centroids (`centroids.py`, cached to `data/domain_centroids.npz`, stamped with model + chunk-file fingerprint and rebuilt when stale), using the retriever's already-loaded BGE model: `< triage_refuse_below` refuses, `>= triage_accept_above` accepts; (3) one LLM yes/no capped at `triage_llm_max_tokens`, only for the band in between. **Fail-open**: if centroids or the LLM are unavailable, the question goes to retrieve. The two thresholds (0.595 / 0.7197) come from `python -m src.eval.triage_sweep` (`eval/triage/sweep.json`); every in-domain golden question is accepted by tier 1, so tier 2 has only been exercised on out-of-scope questions. `refuse_node` is a fixed refusal with no LLM call. Triage also flags in-domain questions that mix 4G-affine and 5G-affine terms (generation affinity measured from the corpus lexicon): it sets `mixed_generation`, `generation_terms` and `retrieval_queries` (a 4G part pinned to 24.301 and a 5G part, via `rewrite_query`), and generate's prompt gets a note to explain the mismatch. Generation terms are acronyms plus two-word phrases ("attach request", "tracking area"; phrase affinity ratio >= 10, >= 20 occurrences, both measured from the corpus). Zero LLM cost. Known gap: `SGW` occurs only 7 times, all in 23.501, so the corpus can't mark it 4G.
- **retrieve** searches `default_top_k` chunks for `query`, or for each query in `retrieval_queries` (a 4G/5G split from triage), round-robin merging and deduplicating split queries. Every retrieved chunk goes to generate: there is no separate sufficiency check (removed 2026-10-23; it spent an LLM call to decide not to answer, and the rewrite it triggered never produced a verified answer in the benchmark).
- `generate_node` is the only LLM call for an in-domain question. Chunk text in its prompt is capped at `prompt_chunk_char_cap` per chunk. The prompt asks for 3-5 sentences using only the source text and its exact 3GPP terms, to say plainly what the sources don't cover, and to **end with one line `STATUS: answered | partial | not_covered`**. `src/generation/answer_status.py` parses and strips that line (missing → `partial`) and runs a **zero-LLM identifier check**: every timer (`T3510`), cause (`#22`) and upper-case message name (`ATTACH REQUEST`) in the answer must appear in the chunk text the model saw, or `answered` is downgraded to `partial` and the identifiers are recorded in `unsupported_identifiers`. No chunks → `not_covered` without an LLM call; an empty reply (a reasoning model can spend all of `generate_max_tokens` thinking and return `content=None`) → `no_answer`. `generate_max_tokens` is 5000 and `generate_reasoning_effort` is `low` (sent to OpenRouter only) since 2026-11-09; at 2000 tokens and the model's default effort, 2 of 29 in-domain answers came back empty. These labels are the model's own, not an independent check: judge correctness against the golden set's expected answers. `app.py`'s `render_assistant_message()` badges each label.
- The generate prompt deliberately hides the retrieval system from the user: a word-boundary banned-phrase gate (`_detect_banned_phrase` in `nodes/core.py`) is a **real gate** — one targeted rephrase attempt, then the leak is allowed to stand. Bare substring matching on "retrieved"/"chunks" was replaced because it false-positived on legitimate 3GPP prose. `<think>` blocks are stripped with regex.
- LLM client selection lives in `nodes/core.py`, read from `.env` at import: `USE_REMOTE_LLM=false` pins a local Ollama endpoint (`localhost:11434`, `qwen3.5:4b`); true picks OpenRouter when `OPEN_ROUTER_API_KEY` is set (or the base URL mentions openrouter), else OpenAI-compatible with `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `MODEL_NAME`. The client itself comes from `make_llm_client()` in `src/obs/tracing.py`. Every node shares one client and model.

**API and deploy (`src/api/`, `Dockerfile`, `deploy/`)** — decisions logged in `docs/phase7-decisions.md`.

- `src/api/main.py` turns HTTP requests into runs of the same graph (with the answer cache, unlike the eval runner). `create_app(graph_factory, balance)` takes injected seams; `tests/test_api.py` uses a fake graph, so no models load in CI. The graph is built once in the FastAPI lifespan and **runs one question at a time behind a lock** (sized for a 2-vCPU free host). `/api/ask` returns `answer`, `status` (= `termination_reason`), `cached`, and `sources` (chunk metadata + an excerpt; table grids flattened). An OpenRouter 402 (out of credit) becomes `503 budget_exhausted`; other LLM errors `502`. `/api/quota` reports the remaining OpenRouter balance, cached `api_budget_cache_seconds`. Per-visitor limits (#64) are not built yet. API settings are the `api_*` fields in `config.py`.
- `/api/ask/stream` runs the graph with `graph.stream(stream_mode="updates")` in one worker thread (keeps the lock and trace context on one thread) and sends SSE: `start`, a `node` event per finished node (`{node, ms, facts}`, facts built in `src/api/events.py`), then `done` (the `AskResponse`) or `error`. The frontend's live route panel depends on these node names and fact keys.
- **Frontend (`frontend/`)** — a one-page pitch site: Pitch → Pipeline diagram → Evals → Demo with a live route panel. Components hold no copy or numbers: text and numbers live in `src/lib/content/*.ts`, section order/nav/API URL in `src/lib/config/site.ts`, colours and type in `src/lib/theme/tokens.css`, guided tours (Driver.js) in `content/tours.ts`, keyed by `data-tour` attributes. `content/demo.ts` `flow.steps` maps backend node names to panel steps. SvelteKit 3 quirks: options go in `vite.config.ts` (no `svelte.config.js`), `#lib` is a config alias (deprecated but working), and any file named `server.*` is treated as server-only (hence `stores/backend.svelte.ts`). The customisation map is in `docs/phase7-decisions.md` → "Frontend build".
- `qdrant_api_key` (empty = local docker Qdrant) is passed by the retriever; set it with `QDRANT_URL` to hit Qdrant Cloud. Retrieval against Cloud matches local (20/29).
- The `Dockerfile` installs CPU-only torch, copies only `src/`, `data/chunks/*_chunks.json` and `data/domain_centroids.npz`, bakes both models in at build time and sets `HF_HUB_OFFLINE=1` — so a changed embed/reranker model or chunk files means rebuilding the image. ~840 MB RAM.
- `deploy/modal_app.py` serves that image on Modal's free plan: at most one container, scales to zero after idle (cold start 20–26 s), secrets from `.env` pushed into the named Modal secret `3gpp-echo-api-env`.

**Observability (`src/obs/`)**

- `logging.py` — `get_logger()` (structlog): JSON lines to `logs/app.jsonl`, pretty console in dev.
- `tracing.py` — tracing is **optional and non-fatal**. With `LANGFUSE_HOST` unset (or `langfuse` not installed), `make_llm_client()` returns a plain `openai.OpenAI` client and tracing helpers are no-ops. With it set (values in `.env.example` match the docker-compose Langfuse), the client is Langfuse-traced. `graph.py` wraps every node in `traced_node()` (one span per node); callers wrap a query in `trace_query()` and attach `trace_attributes(final_state)` so a query is one trace. Independently of Langfuse, every client records each response's token usage to a process-wide log (`usage_snapshot()` / `usage_since()`).
- `metrics.py` — `RunRecorder`, **wired into `src/eval/runner.py`**: per-node latency, node path, tokens (from the usage log, so no Langfuse dependency) and cost estimates (static price table in config, labelled ESTIMATE) per question, written to `eval/runs/<run_id>/`. Not wired into `app.py`.

**Eval (`eval/`, `src/eval/`)** — `eval/golden/golden_set.v1.json` is the canonical, versioned set (18 questions; stable `id`, `type` of `normal | out_of_scope | adversarial`, `gold_clauses`, `retrieval_scored`, `corpus_answerable`, `borderline`), merged from `eval/eval_set.json` and `eval/baseline/gold.json`. Version it rather than editing v1 in place. `golden_set.v2.json` (40 questions: v1's 18 unchanged + 22 new; 29 retrieval-scored, including the 8 traps; adds `answer_quotes`, `generation`, `category`, `wording`, `origin`) is generated from the reviewed `golden_set.v2.draft.md`. The eval scripts default to v1; pass `--golden eval/golden/golden_set.v2.json`. `eval/pooling/v2/` holds the pooled, blind-graded answer key (`grades.json`, 2 = answer / 1 = helpful / 0) plus `supplement_*.jsonl` files graded later. `tests/test_golden_set.py` asserts every `gold_clauses` entry resolves to a real chunk (exact or descendant). `eval/baseline/` is the frozen "before" measurement — its scripts write only inside `eval/baseline/` and shouldn't be changed.

- `src/eval/metrics.py` scores strict and **prefix-credit** matching side by side (a retrieved clause counts if it's the gold clause or a strict descendant — some gold clauses, e.g. `24.501/5.1.3.2`, `23.501/5.15.2`, exist only as descendant chunks), plus nDCG@10 (each gold clause credited once).
- `src/eval/runner.py` supersedes `eval/run_eval.py`: resume keyed by golden-set `id`, refused (`GoldenSetDriftError`) if the golden set's content hash changed; corrupt results raise `ResultsFileCorruptError`; writes are atomic (temp file + `os.replace`); `--limit`/`--types` for cheap iteration; records a `RunRecorder` run. Each result carries `decisions` (how each decision node decided: cache hit, triage tier, mixed generation, unsupported identifiers), each run's `run.json` records the git commit and every non-secret setting (env overrides included), and a one-line result per question is printed (run with `python -u ... > logs/benchmark_live.log` to watch it live). `--golden`, `--ids` and `--max-llm-calls N` (stops before a question whose worst case, 3 calls, could pass the cap; a provider error stops the run) keep runs inside a request budget.
- The "conflation catch rate" metric (`adv_caught = retries > 0`, still in the legacy `run_eval.py` and `app.py`'s dashboard) measured verifier dissatisfaction, not conflation detection — don't report it.
- `src/eval/retrieval_report.py` — zero-LLM-token retrieval scorer: runs `Retriever.search()` against live Qdrant for every `retrieval_scored` question and writes strict + prefix-credit recall@5/@20, MRR, nDCG@10 and p50/p95 latency. Re-run it whenever retrieval, chunking or the golden set changes.
- `src/eval/triage_sweep.py` — zero-LLM-token sweep of triage tier-2 thresholds against the golden set; writes `eval/triage/sweep.json` and `sweep.svg` with recommended `triage_refuse_below` / `triage_accept_above`. Needs the BGE model.

**CI (`.github/workflows/ci.yml`)** — one job on push to `main` and on PRs: `ruff check .` then `pytest tests/ -q` with `USE_REMOTE_LLM=false`. No network, Qdrant or LLM; tests use fakes injected through the node factories and `build_graph()` seams (`tests/test_graph_topology.py` drives the whole compiled graph this way).

## Conventions

- Entry-point scripts append the project root to `sys.path` before importing `src.*`; keep that in any new script.
- Use `get_logger()` from `src/obs/logging.py` instead of `print()` for debug output, payload dumps, and warnings/errors. CLI entry points (`retriever.py`'s `__main__` block, eval reports, missing-dependency messages) still use plain `print()` since that output is the point of running the script.
- Every tunable literal lives in `src/config.py` (`get_settings()`, cached); any field can be overridden by an env var of the same name.
- `spec_id` is bare and dotted (`23.501`, no `TS`); `version` is a separate field (`17.11.0`). Both are passed as chunker CLI args, so a wrong invocation mislabels every chunk from that spec — which has happened: all three specs are labelled `17.11.0`, but 24.501 is 17.12.0 and 24.301 is 17.9.0. Fix with a payload update in place (`set_payload`), not a re-index.
- A full re-index (re-embedding every chunk, about 25 min on CPU) is only needed when the embedding model or the chunk text changes. Reranker changes never need one; junk removal and label fixes are done in place in Qdrant.
- Several files wrap `sys.stdout` in a UTF-8 `TextIOWrapper` — Windows console default encoding breaks on spec text.
- Domain knowledge used at runtime (lexicon, centroids) is **derived from `data/chunks/`**, never hand-written lists.
- Anything that spends real LLM tokens (`src.eval.runner`, `eval/run_eval.py`, `verify.py`, the app) needs an explicit go-ahead before running; prefer `--limit`/`--types` when iterating.

## Planned work (to-dos)

The full production-hardening plan lives in [docs/production-hardening-plan.md](docs/production-hardening-plan.md) — read it before starting any phase. It carries the measured baseline, the defect diagnoses, and the per-phase verification steps.

Measured starting state (frozen in `eval/baseline/`, 18 questions): 1/18 grounded on first pass, 0/6 out-of-scope refusals, 124,701 tokens per run, of which 46,452 (37%) are spent answering questions that should have been refused. Progress is tracked via GitHub issues on `CSroseX/3GPP-Echo` (renamed from `Mavenir-Assignment`) (one epic per phase, one sub-issue per item). **The tracker may lag the code** — issues are often left open after code merges because a checklist item needs a measurement run; verify against the code and the issue's comments before trusting its state.

Measured progress since then (golden set v2, see `DECISIONS.md` and `docs/release-criteria.md`): answer chunk in the top 5 15/29 → 20/29; 1 LLM call per in-domain question. Two consecutive full 40-question runs on 2026-11-09 (single grader): original normal questions 5/6 and 4/6, all normal 15/21 both, traps 4/8 both, off-topic refused 5/5 for free, 0/11 made-up answers, median answer 5–7 s. Release criteria: 9 of 10 met in both runs; the miss is criterion 6, 2 wrong answers labelled "answered" per run (Q24, Q27 both times; bar ≤ 1).

- [x] **Phase 1 — Foundations.** Done: config module (#2), golden set v1 (#3), `@st.cache_resource` (#4), structlog (#5), pinned `pyproject.toml` (#6), prefix-credit scorer + nDCG@10 (#7), golden-set contract test (#8), anchored chunk glob (#9), deterministic `chunk_id` (#10), CI job 1 (#11), committed `eval/baselines/retrieval_baseline.json`.
- [x] **Phase 2 — Reliability and truthful state (#12).** Done, including the clean full run (#21). The verifier, abstain node and retry loop it hardened were later removed (2026-10-25, `DECISIONS.md`).
- [ ] **Phase 3 — Observability (#22).** Done: traced client factory (#24), per-node spans and one trace per query (#25), `RunRecorder` (#26), wired into the runner. Open: #23 — the Langfuse services have never been brought up; #27 — Trace tab, and point the dashboard at `eval/runs/` (likely moot once Streamlit is replaced). To-do: **integrate Langfuse fully** and carry tracing into the FastAPI backend.
- [x] **Phase 4 — Decision-nodes (#28).** Reshaped into the input guardrail (answer cache + triage with a 4G/5G split on acronyms and two-word phrases); refusal and token targets met.
- [ ] **Phase 5 — Retrieval quality (#34).** Done: rerank shortlist (#35), lineage boost (#38), reranker A/B (#37, Ettin 32M adopted), golden set v2 with traps (#39), stemmed BM25 re-tested (no big win, kept off). Remaining misses are first-stage retrieval: 8 of 9 missed answers never reach the top 20. A bigger embedding model is the next candidate, only after a cheap test shows it finds them. Not started: real conflation metric (#41), CI retrieval-regression ratchet (#42). #40 (judge validation) no longer applies: there is no judge.
- [ ] **Phase 6 — Polish (#43).** Nightly / `workflow_dispatch` LLM eval job (#44); README with before/after tables (#45, first version done).
- [ ] **Phase 7 — Public portfolio demo (#59).** FastAPI backend + SvelteKit frontend replacing Streamlit, no login. Done (steps 1–3): FastAPI backend, Dockerfile, deployed on Modal, index copied to Qdrant Cloud. Frontend v1 accepted for shipping (`frontend/`, 2026-11-11; see `docs/phase7-decisions.md` → "Frontend build — v1 shipped"), not deployed; the Modal backend still lacks `/api/ask/stream` until redeployed. Not started: budget protection. Release criteria (#60; bar: ≥4/6 normal questions answered correctly), memory (#61), Dockerfile (#62), production Qdrant (#63), budget protection (#64: 5 questions per visitor by IP /64 + signed cookie, hourly global budget slices #67, cached example answers, visible quotas, provider spend cap), production config (#65), deployment (#66).
