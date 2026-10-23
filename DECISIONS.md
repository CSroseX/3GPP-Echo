# Decision log

A dated record of the decisions that shaped 3GPP-Echo: what we chose, why, and the evidence. Newest last. Negative results are kept on purpose, because a change that was measured and rejected is still a decision.

Issue links point to [CSroseX/3GPP-Echo](https://github.com/CSroseX/3GPP-Echo/issues).

---

### 2026-08-16 · Build on three specs that share vocabulary
**Decision:** Index TS 23.501 (5G architecture), TS 24.501 (5G NAS) and TS 24.301 (4G/EPS NAS).
**Why:** They use the same terms for different procedures. Of 247 acronyms in the 4G spec, 198 also appear in the 5G specs, and 4G says "attach" where 5G says "registration". Mixing up 4G and 5G answers is the realistic failure, so the corpus is built to test it.

### 2026-08-16 · Chunk by document structure, never split tables
**Decision:** Rebuild each spec's clause tree, attach every chunk's chain of parent headings, and keep each table as one chunk.
**Why:** Specs nest up to 7 levels deep (`5.1.3.2.1.2.1`), and 12% of chunks are tables. A chunk without its heading loses its meaning, and half a table is useless.

### 2026-08-17 · Verify every answer against the retrieved text
**Decision:** A second LLM call checks the generated answer, claim by claim, against the retrieved chunks.
**Why:** A fluent answer is not a correct one. In a standards domain, an unsupported claim is worse than no answer.

### 2026-10-01 · Measure before changing anything
**Decision:** Freeze a baseline run in `eval/baseline/` and never edit it.
**Why:** You can't claim an improvement without a fixed "before". The baseline showed 1/18 answers verified, 0/6 off-topic questions refused, and 124,701 tokens per run, 37% of them spent answering off-topic questions.

### 2026-10-01 · Write our own LLM judges, don't use ragas
**Decision:** Custom evaluation code instead of the ragas library.
**Why:** On this Python version, pip could only resolve ragas 0.0.6, a prototype release, and it pulled an old `protobuf`. That's a measured dependency problem, not a preference.

### 2026-10-01 · One versioned test set
**Decision:** Merge the eval questions into `eval/golden/golden_set.v1.json` with stable ids. Changes go into a new version; v1 is never edited.
**Why:** Results are only comparable over time if the questions don't silently change.

### 2026-10-02 · Fix the scorer before tuning retrieval
**Decision:** Count a retrieved sub-clause as a hit for its parent clause ("prefix credit"), reported alongside strict matching.
**Why:** Two gold clauses exist in the corpus only as sub-clauses, so exact matching scored correct retrievals as misses. Tuning against a broken ruler would have optimized the wrong thing.

### 2026-10-02 · Treat an outage differently from a wrong answer
**Decision:** The verifier distinguishes API failures (timeouts, 429s) from "the answer isn't supported".
**Why:** A rate-limit error was counted as a hallucination, burned up to 3 regenerations, and fed "verification could not complete" into the next prompt as if it were critique.

### 2026-10-02 · Abstain instead of showing unverified answers
**Decision:** When an answer can't be verified, return a structured abstention (what was found, which claims failed) instead of the answer.
**Why:** "I can't support this from the specs" is more useful and more honest than a confident wrong answer.

### 2026-10-02 · Make eval runs safe to resume
**Decision:** Resume by question id, refuse to resume if the test set changed, and write results atomically.
**Why:** The old runner resumed by list position and silently restarted from zero on a corrupted file, so results could be paired with the wrong questions.

### 2026-10-02 · Deterministic chunk ids
**Decision:** `chunk_id = sha1(spec | clause | position)`.
**Why:** Re-indexing gives identical ids, so results are reproducible, and two searches can recognise the same chunk.

### 2026-10-05 · Move retrieval inside the pipeline graph
**Decision:** Retrieval is a step in the LangGraph pipeline, not something callers do first.
**Why:** It enables "rewrite the query, then search again". It also removed three call sites that each used a different number of results.

### 2026-10-13 · Refuse off-topic questions cheapest-first
**Decision:** A triage step before retrieval: (1) keyword check, (2) similarity to the specs using a small local model, (3) an LLM yes/no only when (2) is unsure.
**Why:** 37% of the baseline's tokens went to questions like "What is the capital of France?". Most can be refused for free.

### 2026-10-13 · Check the context before generating
**Decision:** Grade whether the retrieved chunks can answer the question. If not, rewrite the query once (deterministically: expand acronyms, split 4G/5G questions), then abstain.
**Why:** 17 of 18 baseline answers failed because the context never contained the answer, and regenerating against the same context can't fix that.

### 2026-10-13 · Optional tracing, independent token accounting
**Decision:** Self-hosted Langfuse for tracing, off unless configured. Token usage is recorded separately to disk for every eval run.
**Why:** The evaluation must still work, and still count cost, when no tracing service is running.

### 2026-10-13 · New retrieval features ship switched off until measured
**Decision:** A bigger rerank shortlist, keyword search (BM25) and a heading-match bonus were added behind settings.
**Why:** The models needed to measure them couldn't be downloaded in that environment. Unmeasured changes shouldn't silently change behaviour.

### 2026-10-22 · Deploy as a public portfolio demo with strict budget protection
**Decision:** No login. 5 questions per visitor (identified by IP and cookie), plus a global budget released in hourly slices, cached answers for example questions, and visible quotas. [#59](https://github.com/CSroseX/3GPP-Echo/issues/59), [#64](https://github.com/CSroseX/3GPP-Echo/issues/64), [#67](https://github.com/CSroseX/3GPP-Echo/issues/67)
**Why:** Without a login, no limit can stop a determined person from returning. So the shared budget must be shaped so that one person can drain at most one hour's slice, not the whole day.

### 2026-10-23 · Repair the index in place instead of re-indexing
**Decision:** Add the missing `chunk_id` to the 4,860 existing points, without re-embedding.
**Why:** We checked first. The vectors were still valid (the embedded text hadn't changed since August) and every point matched exactly one chunk on disk. Only one field was missing, so the fix took seconds instead of a full rebuild.

### 2026-10-23 · FastAPI + SvelteKit for the demo, replacing Streamlit
**Decision:** A FastAPI backend and a SvelteKit frontend.
**Why:** A portfolio demo needs full control over layout and design. A real API also makes rate limiting (client IP, signed cookies) straightforward, and it can stream each pipeline step live.

### 2026-10-23 · Release bar: at least 4/6 normal questions verified
**Decision:** First agreed release criterion. The rest are under discussion in [#60](https://github.com/CSroseX/3GPP-Echo/issues/60).
**Why:** It's clearly better than the baseline (1/6) without overclaiming on an 18-question test set.

### 2026-10-23 · Triage thresholds set from measurement
**Decision:** Refuse below **0.595**, accept from **0.7197** (previously estimated as 0.60 / 0.72).
**Why:** We scored all 18 test questions with the embedding model. The highest off-topic score is 0.575 and the lowest real 3GPP question is 0.740, a clean gap. The estimates turned out almost exactly right.
**Limitation:** Every real question in the test set was already accepted by the keyword check, so the similarity cutoffs have only been tested on off-topic questions. Evidence: `eval/triage/sweep.json`, `sweep.svg`.

### 2026-10-23 · Retrieval defaults chosen from a 9-run comparison
**Decision:** Rerank shortlist **20** (was 40), keyword search **off** (was on), heading bonus **2** (was 0).
**Why:** We measured each change alone and in combination, on the 6 questions with known answers:

| Setup | Correct section in top 5 | Typical search time |
|---|---|---|
| Oct 4 settings (re-measured today) | 0.67 | 1.4 s |
| Defaults until today | 0.50 | 2.8–3.4 s |
| **Chosen** | **0.75** | **1.4 s** |

Times are medians on a laptop CPU. One run overlapped with other work, hence the range.

- Keyword search **lowered** results (0.67 → 0.50). On "Which network function selects the SMF?", it pulled in sections that repeat "SMF" and "network function" and missed the right one, which says "selection", not "selecting".
- A 40-candidate shortlist gave no gain and doubled search time.
- The heading bonus was the only change that helped.

**What this tells us:** the reranker (a general web-search model) is the likely bottleneck, since more candidates gave it more chances to rank wrong sections first. The next step is a reranker comparison ([#37](https://github.com/CSroseX/3GPP-Echo/issues/37)). The features remain in the code, switched off.
**Limitation:** Only 6 questions, and the bonus value was picked on the same questions it's scored on. Evidence: `eval/baselines/ablation_*.json`.
