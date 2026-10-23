# Pooling pilot 2 — results (2026-10-23)

Same 5 questions as pilot 1 (`--ids 1,23,28,31,35`), same corpus and system defaults. Zero LLM tokens.

**Changes from pilot 1** (see `../pilot/RESULTS.md`):
- random chunks dropped;
- added `dense_rewritten`: dense search on the deterministic `rewrite_query` output (acronym expansion; a 4G/5G question becomes two queries, the 4G one pinned to 24.301);
- added `system_neighbours`: the ±1 chunks (same clause) around each of the system's top 10;
- each question's answer chunks are always added, labelled `answer_quote` (not a method).

**Pool:** 293 (question, chunk) pairs. 232 were already graded blind in pilot 1 and keep that grade; the 61 new ones were graded blind here.

## Per-method contribution (5 questions)

| Method | Chunks found | Relevant (≥1) | Answer chunks (2) | Relevant found only by this method | Ranks of relevant |
|---|---|---|---|---|---|
| system | 50 | 14 | 2 | 4 | 1,1,2,3,3,4,5,6,6,7,8,9,10,10 |
| dense per spec | 75 | 10 | 1 | 3 | 4,7,7,8,9,9,9,10,11,15 |
| dense, no reranker | 50 | 10 | 2 | **0** | 1,2,5,6,6,7,8,8,9,10 |
| **dense, rewritten query** (new) | 50 | 10 | 1 | 1 | 2,2,3,4,5,6,7,7,9,9 |
| BM25 + stemming | 50 | 6 | 2 | 2 | 2,2,2,3,4,7 |
| clause-title match | 50 | 4 | 2 | 2 | 1,1,3,10 |
| exact term | 50 | 2 | 0 | 1 | 2,9 |
| **system neighbours (±1)** (new) | 51 | 3 | 0 | 3 | 1,4,5 |
| answer_quote (added, not a method) | 7 | 7 | 6 | — | — |

## Findings

1. **The new methods did not recover any missed answer.** Search methods found 4 of the 7 answer chunks, exactly as in pilot 1.
   The three misses (Q23's registration-type sentence; Q35's 4G T3410 and 5G T3510 sentences) are in the pool only because answer chunks are now always added.
2. **Neighbours add context, not answers:** 3 relevant chunks no other method found (e.g. more of the AMF's function list), none of them an answer.
3. **Dense search without the reranker now adds nothing unique:** everything relevant it finds, the rewritten-query search or another method also finds.
   By the pilot rule ("drop a method that adds nothing unique") it is the one candidate to drop.
4. **Rewritten-query search** finds as many relevant chunks as plain dense search (10), with 1 unique.
5. **The retrieval gap is unchanged:** for Q23 and Q35 no method ranks the answer chunk in its top 10, and neighbours (±1) don't reach it.
