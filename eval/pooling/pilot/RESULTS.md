# Pooling pilot 1 — results (2026-10-23)

**What was run:** `python -m src.eval.pool_candidates --ids 1,23,28,31,35 --out-dir eval/pooling/pilot`
on golden set v2, corpus with bulleted lists indexed (6,124 chunks), system defaults
(shortlist 20, BM25 off, lineage boost 2.0). Zero LLM tokens.

**Pool:** 6 methods × top 10 (dense-per-spec: top 5 per spec) + 3 random chunks per question
= 247 unique (question, chunk) pairs.

**Grading:** blind (from `grading_sheet.jsonl`, no method names), by Claude.
2 = states the answer (quote required), 1 = a fact that helps build the answer, 0 = not useful.
Grades in `grades.json`; ungraded rows default to 0.

## Per-method contribution (5 questions)

| Method | Chunks found | Relevant (≥1) | Answer chunks (2) | Relevant found only by this method | Ranks of relevant |
|---|---|---|---|---|---|
| system (current retriever) | 50 | 14 | 2 | 6 | 1,1,2,3,3,4,5,6,6,7,8,9,10,10 |
| dense per spec | 75 | 10 | 1 | 3 | 4,7,7,8,9,9,9,10,11,15 |
| dense, no reranker | 50 | 10 | 2 | 2 | 1,2,5,6,6,7,8,8,9,10 |
| BM25 + stemming | 50 | 6 | 2 | 2 | 2,2,2,3,4,7 |
| clause-title match | 50 | 4 | 2 | 2 | 1,1,3,10 |
| exact term | 50 | 2 | 0 | 1 | 2,9 |
| random | 15 | 0 | 0 | 0 | — |

## Findings

1. **No method can be dropped:** every search method found at least one relevant chunk no other method found.
2. **Depth 10 is needed:** about half of the relevant chunks sat at ranks 6–10.
3. **The pool missed 2 of 5 answer chunks entirely.**
   - Q23: the answer is at position 4 of the 34 chunks of `24.501/5.5.1.3.2`; the pool held positions 0, 9, 23.
   - Q35: the 4G answer (`24.301/5.5.1.2.2`, position 0 of 12) never surfaced; the 5G answer
     (`24.501/5.5.1.2.2`, position 1 of 20) was missed too (the pool held position 19).
   - ±1 neighbours of pooled chunks would not have reached either answer.
4. **Random chunks (15) found nothing relevant**, so at this size they cannot estimate what the pool misses.
5. **System-side finding:** for Q23 and Q35 no method ranks the answer chunk in its top 10.
   Long sections split into many similar chunks hide the one that answers.
6. **Decoys seen:** the 5G version of a 4G answer (24.501 7.5.1 for Q31) and similarly named IEs
   (EPS update *result* / *type* for EPS update *status*, Q28).

## Changes decided for pilot 2

- Drop random chunks.
- Add the ±1 neighbours (same clause) of the system's top 10.
- Add dense search on the deterministically rewritten query (`rewrite_query`: acronym expansion, 4G/5G split).
- Always add each question's answer chunk(s), labelled `answer_quote`, not counted as a method.
- HyDE: not added (needs LLM tokens; Claude-written passages would leak the gold answers).
