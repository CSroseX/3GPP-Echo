# 3GPP-Echo

A retrieval-augmented assistant that answers telecom questions from three 3GPP specifications: TS 23.501 (5G system architecture), TS 24.501 (5G NAS) and TS 24.301 (4G/EPS NAS).

The three specs were chosen because they share vocabulary but differ in procedure: 4G "attach" vs 5G "registration", the MME vs the AMF. Mixing up 4G and 5G answers is the failure this project is built to measure and prevent. Every design choice, with the measurement behind it, is in [DECISIONS.md](DECISIONS.md).

**Live demo: [3gpp-echo.chitransh-saxena-contact.workers.dev](https://3gpp-echo.chitransh-saxena-contact.workers.dev)** · 5 questions per visitor per day · the first question after an idle spell takes ~20 s while the server wakes.

---

## How a question is answered

```
question
   │
   ▼
cache_lookup ── seen before (and answered)? ──► cached answer, no LLM call
   │
   ▼
triage ── off-topic? ──► fixed refusal, no LLM call
   │       mixes 4G and 5G terms? ──► split into a 4G search and a 5G search
   ▼
retrieve ── dense search in Qdrant, rerank, keep the top 5 chunks
   │
   ▼
generate ── one LLM call: answers from the 5 chunks and labels itself
   │        answered | partial | not_covered
   ▼
cache_store ── keeps only "answered" answers
```

- **One LLM call per question.** There is no separate verifier: it re-read the same chunks, doubled the cost, and rejected correct 4G/5G answers. Instead the model labels its own answer, and a code check (no LLM) downgrades "answered" to "partial" if a timer, cause number or message name in the answer isn't in the retrieved text.
- **Input guardrail.** Off-topic questions are refused for free (keyword check, then embedding similarity, then a tiny LLM yes/no only when unsure). Questions that mix 4G and 5G terms, detected from acronyms and two-word phrases measured in the specs themselves, are searched per generation.
- **Retrieval.** Each spec is rebuilt into its clause tree (tables kept whole, bulleted lists included), embedded with `BAAI/bge-small-en-v1.5`, stored in Qdrant, and reranked with `cross-encoder/ettin-reranker-32m-v1` plus a bonus when the question names a clause's heading. Questions that name a spec or clause are searched only there.

## Measured results

All on golden set v2 (40 questions: 13 5G, 8 4G, 8 mixed 4G/5G traps, 11 off-topic).

| | Start | Now |
|---|---|---|
| Answer chunk in the top 5 (29 retrieval-scored questions) | 15/29 | **20/29** |
| Trap questions with the answer chunk in the top 5 | 1/8 | **4/8** |
| Questions needing 2+ specs with every needed spec in the top 5 (cross-spec coverage) | 3/7 | **6/7** |
| Original 6 normal questions answered correctly (release bar: at least 4/6) | 1/6 | **5/6, 4/6** |
| All 21 normal questions answered correctly | — | **15/21, 15/21** |
| Trap questions answered correctly (mismatch named and explained) | 0 (none passed) | **4/8, 4/8** (+1, +2 partly) |
| Off-topic questions refused with zero LLM calls | 0/6 | **5/5, 5/5** |
| Out-of-scope questions given a made-up answer | — | **0/11, 0/11** |
| Wrong answers labelled "answered" | — | 2, 2 (Q24 and Q27 both times) |
| LLM calls per in-domain question | 2-6 | **1** |
| Answer time, median / 95th percentile | — | **5.2 s / 7.2 s, 7.1 s / 11.6 s** |
| Tokens to run the original 18 questions | 124,701 | **28,780** |

Answer rows show two full runs on 2026-11-09 with identical code and settings (run 1, run 2). Correctness is judged by reading each of the 40 answers against the golden set's expected answer (single grader). Evidence: `eval/runner_results_v2_low5k_full.json` (runs `20261109T081807Z` + `20261109T082841Z`) and `eval/runner_results_v2_low5k_run2.json` (runs `20261109T084441Z` + `20261109T085547Z`). Details and limitations: [DECISIONS.md](DECISIONS.md).

The public demo ships when the [release criteria](docs/release-criteria.md) hold in two consecutive runs. Both runs meet 9 of 10; each gave 2 wrong answers labelled "answered", and the bar is at most 1.

### What we tried (ablations)

Every retrieval change was measured on its own before being kept. Rejected changes are listed too.

| Change | Measured on | Result | Kept? | Evidence (`eval/baselines/`) |
|---|---|---|---|---|
| Rerank 40 candidates instead of 20 | v1, 6 questions | no gain, search time doubled | no | `ablation_*.json` |
| Keyword search (BM25) fused with dense, unstemmed | v1, 6 questions | section recall@5 0.67 → 0.50 | no | `ablation_*.json` |
| Bonus when the question names a clause heading | v1, 6 questions | section recall@5 0.67 → 0.75 | yes | `ablation_G_sl20_nobm25_boost2.json` |
| Index the bulleted lists the parser had dropped (+37% text) | v1, 6 questions | MRR 0.45 → 0.58 | yes | `ablation_list_items.json` |
| Keyword search with stemming, fused with dense | v2, 29 questions | answer in top 5: 15 → 15 (old reranker), 20 → 21 (new) | no, gain too small | `v2_hybrid_stemmed.json`, `v2_ettin32m_bm25.json` |
| Reranker `bge-reranker-base` | v2, 29 questions | 15 → 15, about 6× slower | no | `v2_bge_reranker.json` |
| Guardrail splits mixed 4G/5G questions on phrases too | v2, 29 questions | 16 → 17, traps 2 → 3 | yes | `v2_pipeline_phrases.json` |
| Reranker `ettin-reranker-32m-v1` (512-token cap) | v2, 29 questions | 17 → 20, traps 3 → 4 | yes | `v2_ettin32m.json`, `v2_pipeline_default.json` |

---

## Setup

Requires Python 3.11+, Docker, and an OpenAI-compatible LLM endpoint (OpenRouter is used in development) or a local Ollama.

```bash
python -m venv venv
venv\Scripts\activate            # Windows; on Linux/macOS: source venv/bin/activate
pip install -e ".[ingest,dev]"   # pinned in pyproject.toml

cp .env.example .env             # then fill in your key and model
docker compose up -d qdrant      # Qdrant on :6333
python src/ingestion/indexer.py  # build the index from data/chunks/ (about 25 min on CPU)
```

## Running it

```bash
uvicorn src.api.main:app --port 8000                     # the API the demo calls
cd frontend && npm install && npm run dev                # the site on http://localhost:5173
python src/generation/verify.py "What is the AMF?"       # one question end to end, verbose

# Evaluation
python -m src.eval.retrieval_report --pipeline \
    --golden eval/golden/golden_set.v2.json \
    --grades eval/pooling/v2/grades.json                 # retrieval only, zero LLM tokens
python -m src.eval.runner --golden eval/golden/golden_set.v2.json \
    --max-llm-calls 45                                   # full pipeline, ~35 LLM calls, spends tokens

ruff check . && pytest tests/ -q                         # what CI runs (no network, no LLM)
```

---

## Deployment

```
Browser ──► Cloudflare Workers (static SvelteKit site, frontend/)
   │
   └──► Modal: FastAPI + LangGraph (Dockerfile, models baked in) ──► Qdrant Cloud (6,124 points)
                    │                                              ──► OpenRouter (gpt-oss-20b)
                    └──► Upstash Redis: per-visitor / per-IP daily question counters
```

All free tiers; the only spend is OpenRouter, capped by a credit limit on the API key. Decisions and their reasons: [docs/phase7-decisions.md](docs/phase7-decisions.md).

### Runbook

| Task | How |
|---|---|
| Deploy the frontend | Merge to `main`. Cloudflare Workers Builds runs `npm run build` + `npx wrangler deploy` in `frontend/` (`frontend/wrangler.jsonc`); the API URL comes from `frontend/.env.production`. |
| Deploy the backend | `python deploy/modal_app.py` (reads `.env`, updates the Modal secret, builds the image, deploys). Check from inside the container with `python -m modal run deploy/modal_app.py::check` (no LLM tokens). |
| Roll back the frontend | Cloudflare dashboard → the `3gpp-echo` Worker → Deployments → pick an earlier version → Rollback. |
| Roll back the backend | `git checkout <good commit>` then `python deploy/modal_app.py`; or Modal dashboard → the app → Deployments → roll back. |
| Rotate the OpenRouter key | Create a new key (with a credit limit) on OpenRouter, put it in `.env` as `OPEN_ROUTER_API_KEY`, run `python deploy/modal_app.py`, then delete the old key. |
| Allow another frontend URL | Add it to `API_CORS_ORIGINS` in `.env` (a JSON list) and redeploy the backend. |
| Change the daily limits | `QUOTA_PER_VISITOR_DAY` / `QUOTA_PER_IP_DAY` in `.env`, then redeploy the backend. |
| Keep Qdrant Cloud alive | The `qdrant-keepalive` GitHub Action searches every 3 days (free clusters are suspended after a week idle). Run it by hand from the Actions tab to check. |
| Rebuild Qdrant Cloud if lost | Start local Qdrant (`docker compose up -d qdrant`, index present) and run `python deploy/copy_qdrant.py`: seconds, no re-embedding. |

## What's next

- **Frontend v2**: more polish on the live site; record the example questions so their cards replay for free.
- **Budget**: optional hourly slices of the global budget ([#67](https://github.com/CSroseX/3GPP-Echo/issues/67)); today the OpenRouter key's credit limit is the global cap.
- **Observability**: bring up the self-hosted Langfuse tracing ([#23](https://github.com/CSroseX/3GPP-Echo/issues/23)) and carry it into the FastAPI backend.
- **Quality**: the remaining misses are first-stage retrieval (8 of 9 missed answers never reach the top 20) and answers the model labels "not covered" too readily. Candidates: a bigger embedding model, and Qdrant's native sparse vectors as a keyword index inside the database (the in-process BM25 above needs no re-index, which is why it was tried first).

## Limitations

- The golden set is small (40 questions) and graded by one reviewer; numbers move by one question at a time.
- The model's status label is not an independent check: it can call a wrong answer "answered".
- Answers vary between runs even at temperature 0, because OpenRouter routes the same model to different hosting providers.
