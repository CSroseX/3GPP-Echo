# Release criteria for the public demo (#60)

Set on 2026-10-25 from the full golden-set v2 benchmark (`eval/runs/20261025T090844Z`). Each threshold sits slightly below what was measured, so it is honest and reachable. **The demo ships when every criterion holds in two consecutive full runs** (answers vary between runs, so one good run isn't enough).

How to measure: `python -m src.eval.runner --golden eval/golden/golden_set.v2.json --max-llm-calls 39`, then read each answer against the golden set's `expected_behavior` and `answer_quotes`. Speed and tokens come from the run's `summary.json` / `per_question.jsonl`.

| # | Criterion | Threshold | Measured 2026-10-25 | Status |
|---|---|---|---|---|
| 1 | Original 6 normal questions answered correctly | ≥ 4/6 in every run | 5/6 | met |
| 2 | All 21 normal v2 questions answered correctly | ≥ 15/21 | 16/21 | met |
| 3 | 4G/5G trap questions answered correctly (mismatch named and explained) | ≥ 4/8 | 4/8 (+1 partly) | met, no margin |
| 4 | Obvious off-topic questions refused with zero LLM calls | 5/5 | 5/5 | met |
| 5 | Out-of-scope questions given a made-up answer | 0/11 | 0/11 | met |
| 6 | Answers labelled "answered" that are wrong | ≤ 1 per run | 1 (Q27) | met, no margin |
| 7 | Empty answers (`no_answer`) | ≤ 1 per 29 in-domain questions | 2 | **not met** |
| 8 | No rebuild of `data/domain_centroids.npz` (or any model artifact) on a visitor's request | 0 | rebuilt on the first off-topic question (about 21 min) | **not met** |
| 9 | Answer time | median < 15 s, 95th percentile < 40 s | 9.8 s / 34 s | met |
| 10 | Tokens per question that reaches the LLM | < 3,000 average | about 2,600 (91,810 over 35) | met |

Criteria 3 and 6 are met with no margin; a single changed answer breaks them. Criterion 8 also covers the hosting setup: model artifacts must be built before the app serves traffic.

Not part of this list but required for the deployment itself (tracked in #61–#67): memory and cold start (#61), budget protection (#64, #67), production config (#65).
