# 3GPP-Echo

**A retrieval-augmented assistant that answers 3GPP telecom questions only from what the specifications actually say, and says so when they don't.**

[![CI](https://github.com/CSroseX/3GPP-Echo/actions/workflows/ci.yml/badge.svg)](https://github.com/CSroseX/3GPP-Echo/actions/workflows/ci.yml)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-1.19-DC244C?style=for-the-badge&logo=qdrant&logoColor=white)
![FastEmbed](https://img.shields.io/badge/FastEmbed-BGE--small-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)
![Cross-Encoder](https://img.shields.io/badge/Cross--Encoder-MiniLM--L6-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)
![BM25](https://img.shields.io/badge/BM25-RRF%20hybrid-6E40C9?style=for-the-badge)
![Docling](https://img.shields.io/badge/Docling-PDF%20parsing-052FAD?style=for-the-badge)

![OpenAI-compatible](https://img.shields.io/badge/LLM-OpenAI--compatible-412991?style=for-the-badge)
![Ollama](https://img.shields.io/badge/Ollama-local-000000?style=for-the-badge&logo=ollama&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Langfuse](https://img.shields.io/badge/Langfuse-tracing-0A0A0A?style=for-the-badge)
![Pydantic](https://img.shields.io/badge/Pydantic-settings-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-308%20tests-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)
![Ruff](https://img.shields.io/badge/Ruff-lint-D7FF64?style=for-the-badge&logo=ruff&logoColor=black)

---

## Why this exists

3GPP-Echo is grounded in three specifications:

| Spec | Scope |
|---|---|
| **TS 23.501** | 5G System architecture |
| **TS 24.501** | 5G NAS (5GMM / 5GSM) |
| **TS 24.301** | EPS (4G) NAS |

They were picked on purpose. They share most of their vocabulary (registration, tracking area, GUTI, bearer, session) but differ in procedural detail. A model that blends a 4G procedure into a 5G answer sounds fluent and is wrong. **Cross-spec conflation is the failure mode this system is built to defeat.** Every design choice below is about refusing to say something the retrieved text does not support.

## How it works

Ingestion runs once and caches its outputs. At query time a single LangGraph state machine does everything: it decides whether the question is in scope, retrieves, judges whether the evidence is enough, rewrites the query once if not, then generates and verifies.

```
START → triage ──out of scope──→ refuse → END
          │ in scope
          ↓
       retrieve → grade_sufficiency ──not enough, rewrite left──→ rewrite_query → retrieve
                        │            ──not enough, exhausted─────→ abstain → END
                        │ enough
                        ↓
                    generate → verify ──supported──→ END
                                  │ unsupported, retries left → generate (with feedback)
                                  │ unsupported, exhausted / verifier down → abstain → END
```

### 1. Ingestion (`src/ingestion/`)

- **Parse:** Docling extracts text, headings and tables from the spec PDFs.
- **Rebuild the clause tree:** a depth stack over clause numbers (`5.3.4` has depth 3) restores each clause's full lineage, including letter-suffixed clauses such as `4.2.8.1A`.
- **Chunk by clause:** chunks respect clause boundaries, with a 400-token soft limit and an 800-token hard cap. Tables are never split; each table is one chunk holding its raw grid.
- **Index:** each chunk is embedded with a lineage header (`Spec 23.501 17.11.0 Clause 6.2.1 AMF`) using `BAAI/bge-small-en-v1.5`. The whole chunk is stored as the Qdrant payload, under a deterministic `chunk_id`.

The result is 4,860 chunks across the three specs.

### 2. Retrieval (`src/retrieval/`)

- **Targeting:** a question that names a spec (`TS 23.501`) or a clause (`clause 5.5`) is filtered to it. Clause filters include every sub-clause.
- **Hybrid first stage:** dense Qdrant search plus an in-process BM25 index, fused with Reciprocal Rank Fusion. BM25 catches exact acronyms (NSSAI, T3412) that dense embeddings miss.
- **Rerank:** `cross-encoder/ms-marco-MiniLM-L-6-v2` scores `8 × top_k` candidates.
- **Lineage boost:** optional and off by default (see Limitations).

### 3. Decision graph (`src/generation/`)

| Node | What it decides | Cost |
|---|---|---|
| `triage` | In scope or not, in three tiers, cheapest first: corpus-derived lexicon, then embedding similarity to per-spec clause centroids, then a yes/no LLM call only for the ambiguous band | Usually zero LLM calls |
| `refuse` | Fixed out-of-scope answer | None |
| `retrieve` | Hybrid search for the question, or for each rewritten query | No LLM |
| `grade_sufficiency` | Can this context answer the question at all? A cross-encoder floor, then one binary relevance call over the top 5 chunks | 0–1 LLM call |
| `rewrite_query` | Deterministic, capped at one: expands acronyms both ways from the corpus lexicon and splits mixed 4G/5G questions, pinning the 4G part to TS 24.301 | No LLM |
| `generate` | Answers only from the chunks it was given | 1 LLM call |
| `verify` | Strict entailment judge at temperature 0; unsupported claims go back to `generate` as feedback | 1 LLM call |
| `abstain` | Structured "I can't support that": which clauses were found, which claims failed, and why | None |

The lexicon and the centroids are derived from the chunk files, never hand-written. Every routing decision is a pure function in `routers.py`, unit-tested without a graph or a model.

### 4. Evaluation and observability (`src/eval/`, `src/obs/`)

- **Golden set** (`eval/golden/golden_set.v1.json`): 18 versioned questions, tagged `normal`, `adversarial` (4G/5G traps) or `out_of_scope`, with gold clauses. A contract test checks that every gold clause exists in the corpus.
- **Retrieval report:** strict and prefix-credit recall@5/@20, MRR, nDCG@10 and latency. Spends zero LLM tokens.
- **Eval runner:** resumes by question id, refuses to resume if the golden set changed, writes atomically, and records per-node latency, tokens and estimated cost to `eval/runs/<run_id>/`.
- **Tracing:** optional. Point `LANGFUSE_HOST` at a Langfuse instance and every query becomes one trace with one span per node. Without it, nothing changes.

## Results

**Before:** the frozen baseline in `eval/baseline/`, measured on the original `generate → verify` pipeline over the 18-question set.

| Metric | Before | After |
|---|---|---|
| Answers verified on first pass | 1 / 18 | pending (#21) |
| Out-of-scope questions refused | 0 / 6 | pending (#21) |
| Tokens per 18-question run | 124,701 | pending (#21) |
| Tokens spent on questions that should have been refused | 46,452 (37%) | pending (#21) |

Retrieval baseline (6 retrieval-scored questions):

| | recall@5 | recall@20 | MRR |
|---|---|---|---|
| Strict clause match | 0.583 | 0.750 | 0.468 |
| Prefix credit (sub-clauses count) | 0.667 | 0.917 | 0.523 |

**Where "after" stands:**

- **Out-of-scope refusals:** the decision nodes are merged. With test doubles, "What is the capital of France?" now ends at `refuse` with zero LLM calls. The real-model numbers above need one full eval run, which spends tokens and is waiting on a go-ahead.
- **Retrieval ablation:** the hybrid search, candidate pool and lineage boost changes each need their own `retrieval_report` run. That table will land here.
- **First signal:** BM25 alone puts Q6's gold clause `23.501/5.15.2` at rank 1, where dense retrieval missed it in its top 20.

## Quickstart

**Requirements:** Python 3.11+, Docker, and either an OpenAI-compatible API key (OpenAI, OpenRouter, Groq, ...) or a local Ollama.

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # extras: ingest (Docling), obs (Langfuse)

# 2. Configure the LLM
cp .env.example .env               # set USE_REMOTE_LLM, OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME

# 3. Start Qdrant and index the bundled chunk files
docker compose up -d qdrant
python src/ingestion/indexer.py

# 4. Ask questions
streamlit run app.py               # chat UI + eval dashboard
python src/generation/verify.py "What is the role of the AMF in the 5G system architecture?"
```

Re-parsing the PDFs is only needed if you change the chunking. Each ingestion stage is a separate command (`parse.py` → `tree_builder.py` → `chunker.py` → `indexer.py`); see `CLAUDE.md` for the exact invocations.

## Evaluation

```bash
# Zero LLM tokens
python -m src.eval.retrieval_report --output eval/baselines/ablation_<name>.json
python -m src.eval.triage_sweep                     # tunes triage thresholds; writes eval/triage/

# Spends LLM tokens
python -m src.eval.runner --limit 3                 # cheap smoke run
python -m src.eval.runner                           # full 18 questions
```

Every setting in `src/config.py` can be overridden by an environment variable of the same name, which is how ablations run:

```bash
HYBRID_BM25=false python -m src.eval.retrieval_report --output eval/baselines/ablation_dense_only.json
LINEAGE_BOOST=1.0 python -m src.eval.retrieval_report --output eval/baselines/ablation_lineage_1.json
```

## Observability

```bash
docker compose up -d               # Qdrant + self-hosted Langfuse on http://localhost:3000
```

Then add the three `LANGFUSE_*` lines from `.env.example` to `.env`. They match the project that docker-compose provisions on first boot.

Each query appears as one trace with a span per node. Each span carries `termination_reason`, `attempt`, `top1_cross_score`, `n_relevant_chunks` and `triage_decision`. Token usage is recorded independently of Langfuse, so eval runs count tokens even with tracing off.

## Configuration

| Setting | Default | Effect |
|---|---|---|
| `DEFAULT_TOP_K` | 5 | Chunks passed to generation |
| `RERANK_MULTIPLIER` | 8 | Candidates reranked = multiplier × top_k |
| `HYBRID_BM25` | true | Fuse BM25 with dense retrieval |
| `LINEAGE_BOOST` | 0.0 | Weight of the clause-title match boost |
| `MAX_RETRIES` | 3 | Generate/verify grounding retries |
| `MAX_REWRITES` | 1 | Query rewrites before abstaining |
| `TRIAGE_REFUSE_BELOW` / `TRIAGE_ACCEPT_ABOVE` | 0.60 / 0.72 | Triage embedding thresholds (provisional) |
| `SUFFICIENCY_MIN_RELEVANT` | 2 | Relevant chunks needed to generate |

## Project layout

```
app.py                     Streamlit chat UI and eval dashboard
src/config.py              Every tunable, via pydantic-settings
src/ingestion/             parse → tree_builder → chunker → indexer (+ chunk_ids)
src/retrieval/             retriever, BM25 + RRF (hybrid), lineage boost
src/generation/            graph, routers, state, lexicon, centroids
src/generation/nodes/      triage, retrieve, grade, rewrite, generate/verify, abstain
src/eval/                  metrics, runner, retrieval_report, triage_sweep
src/obs/                   structlog logging, tracing factory, RunRecorder
eval/golden/               versioned golden set
eval/baseline/             frozen "before" measurement
tests/                     308 tests, no network, no Qdrant, no LLM
docs/                      production-hardening plan
```

## Design decisions

- **Custom judges, not ragas.** This was measured, not a preference: with dependencies resolved, pip backs off from ragas 0.4.3 to the 0.0.6 prototype and drags in `protobuf 3.20.0`. The verifier and the relevance grader are small, typed, unit-tested judges instead.
- **Outages are not hallucinations.** The verifier separates transport failures (429s, timeouts) from "this claim is unsupported". An outage ends in an honest `verifier_unavailable` abstention instead of burning retries and feeding a fake critique back to the generator.
- **Abstaining is a feature.** When the context cannot answer, the graph stops before generating instead of regenerating three times against evidence that was never there.
- **Domain knowledge comes from the corpus.** Acronyms, long forms, title bigrams, 4G/5G affinity and scope centroids are all derived from `data/chunks/`.
- **Tracing never breaks a query.** Langfuse is optional at every level, and the offline eval gate does not depend on it.

## Limitations

- **The after-numbers are not in yet.** The decision graph and retrieval changes are tested with test doubles. Their real-model and real-reranker effects need the eval runs listed under Results.
- **Triage thresholds are provisional** until `triage_sweep` runs. The configured reasoning model may also return an empty answer at a 10-token cap, in which case ambiguous questions fail open to retrieval.
- **The lineage boost is off.** It lifts the right clause for "the AMF", but it also fully matches decoys such as the 4G `24.301` "GUTI" clause for a 5G-GUTI question, which is exactly the conflation this project fights. It stays off until a sweep picks a safe weight.
- **The adversarial metric is not real yet.** "Conflation caught" currently means "the verifier retried", which measures dissatisfaction, not detection. The 6 adversarial questions still need gold labels.
- **The judge is unvalidated.** No human agreement score (Cohen's κ) exists for the verifier yet; with a 1/18 first-pass baseline it is probably over-strict.
- **Small golden set.** 18 questions, of which 6 are retrieval-scored, so one label moves a mean by several points.
- **Future work:**
  - Qdrant-native sparse vectors instead of in-process BM25 (needs a reindex).
  - A reranker A/B test against `bge-reranker-base`.
  - A CI retrieval-regression ratchet.
  - A nightly LLM eval.

Reranker fine-tuning was left out on purpose: 18 questions would overfit it.
