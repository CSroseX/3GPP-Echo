# 3GPP-Echo

A retrieval-augmented assistant that answers telecom questions from three 3GPP specifications: TS 23.501 (5G system architecture), TS 24.501 (5G NAS) and TS 24.301 (4G/EPS NAS).

The three specs were chosen because they share vocabulary but differ in procedure: 4G "attach" vs 5G "registration", the MME vs the AMF. Mixing up 4G and 5G answers is the failure this project is built to measure and prevent. Every design choice, with the measurement behind it, is in [DECISIONS.md](DECISIONS.md).

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
| Normal questions answered correctly (release bar: at least 4/6) | 1/6 | **5/6** |
| Trap questions answered correctly | 0 (none passed) | **5/8** |
| LLM calls per in-domain question | 2-6 | **1** |

Answer correctness is judged by reading each answer against the golden set's expected answer (single grader, 14 questions). Details and limitations: [DECISIONS.md](DECISIONS.md).

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
streamlit run app.py                                     # chat UI (being replaced, see below)
python src/generation/verify.py "What is the AMF?"       # one question end to end, verbose

# Evaluation
python -m src.eval.retrieval_report --pipeline \
    --golden eval/golden/golden_set.v2.json \
    --grades eval/pooling/v2/grades.json                 # retrieval only, zero LLM tokens
python -m src.eval.runner --golden eval/golden/golden_set.v2.json \
    --max-llm-calls 20                                   # full pipeline, spends tokens

ruff check . && pytest tests/ -q                         # what CI runs (no network, no LLM)
```

---

## What's next

- **Public portfolio demo** ([#59](https://github.com/CSroseX/3GPP-Echo/issues/59)): a FastAPI backend and a SvelteKit frontend replacing Streamlit, deployed without a login.
- **Budget protection** ([#64](https://github.com/CSroseX/3GPP-Echo/issues/64), [#67](https://github.com/CSroseX/3GPP-Echo/issues/67)): 5 questions per visitor, a global budget released in hourly slices, cached example answers, visible quotas and a provider spend cap.
- **Observability**: bring up the self-hosted Langfuse tracing ([#23](https://github.com/CSroseX/3GPP-Echo/issues/23)) and carry it into the FastAPI backend.
- **Quality**: the remaining misses are first-stage retrieval (8 of 9 missed answers never reach the top 20) and answers the model labels "not covered" too readily.

## Limitations

- The golden set is small (40 questions) and graded by one reviewer; numbers move by one question at a time.
- The model's status label is not an independent check: it can call a wrong answer "answered".
- Answers vary between runs even at temperature 0, because OpenRouter routes the same model to different hosting providers.
