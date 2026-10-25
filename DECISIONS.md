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

### 2026-10-23 · Index bulleted lists, which were silently dropped
**Decision:** The step that rebuilds each spec's structure now includes bulleted lists. The index was rebuilt, growing from 4,860 to 6,124 chunks.
**Why:** While drafting test questions, we noticed sentences ending in "the following functionality:" followed by nothing. The PDF parser stores lists separately, and our code skipped them, so about 37% of the spec text never reached search. 3GPP specs put most of their substance in lists: the AMF section had its introduction but none of the AMF's functions. The PDF didn't need re-parsing, because the lists were already in the parsed output.

| Measure (6 questions) | Before | After |
|---|---|---|
| Correct section in top 5 | 0.75 | 0.75 |
| Rank quality (MRR) | 0.45 | 0.58 |
| Rank quality (nDCG@10) | 0.50 | 0.63 |
| Typical search time | 1.4 s | 1.7 s |

Correct sections moved up (AMF: position 11 → 6; PDU session: 2 → 1; SMF selection: 4 → 2), although none newly entered the top 5. The bigger expected gain is in answers, since the model now sees the list text; that needs an LLM run to measure.
**Limitation:** Only 6 questions. Search time rose about 25%, probably because longer chunks give the reranker more text to read. Evidence: `eval/baselines/ablation_list_items.json` vs `ablation_G_sl20_nobm25_boost2.json`.

### 2026-10-24 · Split mixed 4G/5G questions on phrases, not only acronyms
**Decision:** The input guardrail splits a question that mixes 4G and 5G into a 4G search and a 5G search. It now recognises two-word phrases ("attach request", "tracking area") as well as acronyms, and each half of the split drops the other generation's terms.
**Why:** The guardrail only recognised acronyms (MME, AMF), so "What is the message format for a 5G Session Management Tracking Area Update?" was never split: "Tracking Area Update" is a 4G procedure written in plain words. Which generation a phrase belongs to is counted from the spec text, not hand-written: "tracking area updat…" appears 1,227 times in the 4G spec and 57 times in the two 5G specs.

| Answer chunk in top 5 (golden set v2, 29 questions) | All | 5G | 4G | 4G/5G traps |
|---|---|---|---|---|
| Question searched as typed (previous scoring) | 15/29 | 8/13 | 6/8 | 1/8 |
| Through the guardrail, acronyms only | 16/29 | 8/13 | 6/8 | 2/8 |
| **Through the guardrail, acronyms + phrases** | **17/29** | 8/13 | 6/8 | **3/8** |

The guardrail now splits 7 of the 8 traps (was 5), and no normal question is split by mistake. Search time 1.5 s → 1.6 s. We also learned that the retrieval report had been searching the question as typed, skipping the guardrail, so it understated what the app does; `retrieval_report --pipeline` now searches the way the app does.
**Limitation:** Only 8 trap questions, and the answer key has a single grader. "SGW" appears only 7 times in the corpus, all in the 5G spec, so counts alone can't mark it 4G. Four traps are split correctly but still miss their answer (Q7, Q8, Q9, Q11). Evidence: `eval/baselines/v2_pipeline_before.json` vs `v2_pipeline_phrases.json`.

### 2026-10-24 · Replace the reranker with a small modern one (Ettin 32M)
**Decision:** Rerank with `cross-encoder/ettin-reranker-32m-v1` instead of `ms-marco-MiniLM-L-6-v2`, reading at most 512 tokens per chunk.
**Why:** Earlier measurements pointed at the reranker as the bottleneck: better candidates reached the shortlist but weren't ranked into the top 5. A published comparison on one CPU (Hugging Face, May 2026) showed the small Ettin models beating MiniLM at similar cost. We measured on our own questions, searching the way the app does, with every top-5 chunk graded:

| Reranker | Answer chunk in top 5 (29 questions) | 5G | 4G | 4G/5G traps | Typical search time |
|---|---|---|---|---|---|
| MiniLM-L6 (previous) | 17/29 | 8/13 | 6/8 | 3/8 | 1.6 s |
| bge-reranker-base | no gain (tested earlier, without the guardrail) | | | | ~6× slower |
| Ettin 17M | 18/29 | 9/13 | 6/8 | 3/8 | 1.2 s |
| **Ettin 32M** | **20/29** | **10/13** | 6/8 | **4/8** | 2.2 s |

"What is the role of the AMF?", which had missed since the first baseline, now finds its answer at rank 2 (was 6).
- **bge-reranker-base was rejected:** no gain, about 6× slower. It also outputs scores between 0 and 1, so our +2.0 heading bonus overrode it; a reranker's score scale has to be checked before comparing. Ettin outputs scores on a scale like MiniLM's, so the bonus keeps its meaning.
- **Why the 512-token cap:** Ettin can read 8,000 tokens, and our unsplit table chunks reach about 10,000. That made some searches take 20–35 s. Capping at 512 (MiniLM's limit) kept 20/29 and brought the slowest searches from 22.9 s to 4.4 s.

**Limitation:** 29 questions and a single grader. Rerankers that surfaced chunks the answer key had never seen were held until those chunks were graded (56 in total, none an answer). Evidence: `eval/baselines/v2_pipeline_phrases.json` vs `v2_ettin32m.json`, `v2_pipeline_default.json`.

### 2026-10-25 · Removed the verifier: one LLM call per question, self-labelled
**Decision:** Each answer now comes from a single LLM call. The model ends its answer with `STATUS: answered | partial | not_covered`, and the app shows that label. The separate verifier call and its retry loop are gone. A code check with no LLM backs up the label: every timer (T3510), cause number (#22) and message name (ATTACH REQUEST) in the answer must appear in the spec text the model was given, otherwise "answered" becomes "partial". Only "answered" answers are cached.
**Why:** The verifier was a second LLM call reading the same chunks the first call had already seen, so it added cost without new information. Its retry regenerated the answer from those same chunks, and at our benchmark setting it never actually ran. On the 4G/5G trap questions it did harm: it rejected correct answers like "the MME is a 4G entity; the UDM is 5G", because no chunk states that literally.

| Same 14 questions (6 normal, 8 traps) | With verifier (2026-10-24) | Self-labelled (2026-10-25) |
|---|---|---|
| LLM calls | 31 | **14** |
| Tokens | ~76,000 | **33,688** |
| Time per answer | ~20 s | **~11 s** |
| Normal answers correct (release bar: at least 4/6) | 5/6 verified | 4/6 correct |
| Trap answers reaching the user as correct | 0/8 passed | **3/8 correct**, 2 partly |

The difference between 5/6 and 4/6 is within run-to-run variation; the answers change slightly each time.

**Limitation:** A label the model gives itself is not an independent check. Q5 was labelled "answered" while containing an error (it lists 5GMM-CONNECTED as a state, but it's a mode). Q6 and Q7 were labelled "not covered" even though search had found the answer. The identifier check only catches wrong identifiers, not wrong explanations. Correctness was judged by reading each answer against the golden set's expected answer, by a single grader, on 14 questions. Evidence: `eval/runs/20261024T122927Z` and `20261024T123722Z` (verifier) vs `20261024T203715Z` (self-labelled).

### 2026-10-25 · Full benchmark on golden set v2; release criteria set from it
**Decision:** The full 40-question run below is the measured state the demo is released against. The release criteria in [docs/release-criteria.md](docs/release-criteria.md) are set slightly below these numbers, so the bar is honest and reachable. Every criterion must hold in two consecutive runs, because answers vary between runs.
**Why:** The earlier bar ("at least 4/6 verified") covered only 6 questions and depended on the verifier, which no longer exists. This run covers all 40 questions, including the 22 added in v2.

| Measure | Frozen baseline (2026-10-01, 18 questions) | Full v2 run (2026-10-25) |
|---|---|---|
| Original 6 normal questions answered correctly | 1/6 | **5/6** |
| Off-topic questions refused (original set) | 0/6 | **5/5, zero LLM cost** |
| Tokens for the original 18 questions | 124,701 | **35,894** |
| All 21 normal v2 questions correct | — | **16/21** |
| 4G/5G traps correct | — | **4/8**, 1 partly |
| Out-of-scope v2 questions with a made-up answer | — | **0/11** |
| Empty answers | — | 2/29 |
| Answer time, median / 95th percentile | — | 9.8 s / 34 s |

What drove the gains, each measured in the entries above: the bulleted-list fix (37% of the text had been missing), the Ettin reranker and the phrase-based 4G/5G split (answer chunk in top 5: 15/29 → 20/29), one self-labelled LLM call instead of a verifier loop, and the prompt that accepts answers in different words.
**Limitation:** One run, one grader. Known weak spots: 2 empty answers (the model spends its 2,000-token allowance thinking), trap answers that vary between runs (OpenRouter routes the model to different hosts), off-topic questions that sound like telecom cost one LLM call each, and the off-topic reference vectors (`data/domain_centroids.npz`) had gone stale after the re-index, so the first off-topic question rebuilt them (about 21 minutes). Evidence: `eval/runs/20261025T090844Z`, `eval/runner_results_v2_full.json`.
