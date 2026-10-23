# Pooling — full run on golden set v2 (2026-10-23)

**What was run:** `python -m src.eval.pool_candidates --out-dir eval/pooling/v2` over all 29 retrieval-scored
questions of golden set v2 (corpus: 6,124 chunks with bulleted lists; system defaults: shortlist 20,
BM25 off, lineage boost 2.0). Zero LLM tokens.

**Methods (top 10 each; dense per spec = top 5 per spec):** dense per spec, dense on the rewritten query,
BM25 with stemming, exact term, clause title, current system, ±1 neighbours of the system's top 10.
Dense search without the reranker was dropped after pilot 2 (it added nothing unique).
Each question's answer chunks are always added, labelled `answer_quote` (not a method).

**Pool:** 1,586 (question, chunk) pairs.

**Grading:** blind, by Claude, 2 / 1 / 0 (answer / helpful fact / not useful). Grades for the 5 pilot questions are
carried over from pilots 1–2. For the other 24, each chunk was read as its opening plus the passages that best
match the question's words; every answer chunk was checked in full. **Limitations:** one grader, no second
opinion yet (Cohen's κ, #40), and a relevant fact deep inside a long chunk may be under-graded. 168 non-zero
grades, 47 of them grade 2.

## Per-method contribution (29 questions)

| Method | Chunks found | Relevant (≥1) | Answers (2) | Relevant found only by this method | Answers found only by this method |
|---|---|---|---|---|---|
| current system | 290 | 78 | 24 | 12 | 2 |
| dense per spec | 435 | 69 | 21 | 10 | 1 |
| BM25 + stemming | 290 | 59 | 22 | 9 | 2 |
| dense, rewritten query | 290 | 59 | 19 | 6 | 1 |
| exact term | 281 | 36 | 14 | 12 | 1 |
| clause title | 290 | 25 | 9 | 4 | 0 |
| system neighbours (±1) | 284 | 21 | 3 | 17 | 2 |

## Pool completeness

- 47 answer chunks (grade 2) in the pool; **36 were found by at least one search method, 11 only because answer chunks are always added.**
- For 5 questions no search method found any answer chunk: **Q9, Q11, Q12** (v1 traps), **Q23** (5G, answer in chunk 5 of a 34-chunk section) and **Q35** (trap: T3510 vs T3410).

## What the current system gets right (chunk level, against this answer key)

| Method | Answer chunk in top 5 | Answer chunk in top 10 | Any relevant chunk in top 5 |
|---|---|---|---|
| current system | 15/29 | 18/29 | 25/29 |
| BM25 + stemming | 15/29 | 16/29 | 22/29 |
| dense, rewritten query | 11/29 | 15/29 | 19/29 |

By question type, the system's answer chunk in top 5: **5G 8/13, 4G 6/8, mixed 4G/5G traps 1/8**.
BM25 with stemming does as well overall and better on 4G (7/8) and traps (2/8).
(Dense-per-spec is left out of this table: its ranks restart in each spec, so "top 5" isn't comparable.)

## Findings

1. **Traps are the weak spot:** the system puts an answer chunk in its top 5 for only 1 of 8 mixed 4G/5G questions — the failure this corpus was built to expose.
2. **Stemmed BM25 matches the system on its own** (15/29 in top 5). The earlier result that BM25 hurts (DECISIONS.md, 2026-10-23) used unstemmed BM25, 6 questions and the old corpus; fusion with stemmed BM25 should be re-tested on v2.
3. **Every method adds something unique**, so all stay in the pool for future re-pooling.
4. **Neighbours add context, not answers** (17 unique relevant chunks, only 2 unique answers).
