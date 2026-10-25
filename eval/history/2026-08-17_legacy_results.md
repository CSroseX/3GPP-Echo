# Legacy eval results, 2026-08-17 (deleted `eval/results.json`)

Written by the original `eval/run_eval.py` in commit `7c7b9ad` ("Final eval tests"). The file was deleted on 2026-10-25 (#21) because it was misleading and nothing current depended on it except the old Streamlit dashboard tab. The full file stays in git history: `git show 7c7b9ad:eval/results.json`.

## What it contained

12 of the 18 golden-set v1 questions (the 6 normal and 6 adversarial ones). The run never reached the 6 out-of-scope questions.

| # | Type | Recorded status | Recorded retries | Answer, in short |
|---|---|---|---|---|
| 1 | normal | verified_after_retry | 1 | AMF: N2 termination, registration/connection/mobility management |
| 2 | normal | verified_after_retry | 2 | UE builds PDU SESSION ESTABLISHMENT REQUEST (step list) |
| 3 | normal | verified_after_retry | 1 | The AMF selects the SMF |
| 4 | normal | verified_after_retry | 1 | 5G-GUTI = GUAMI + 5G-TMSI |
| 5 | normal | verified_after_retry | 1 | 5GMM state machines per access type |
| 6 | normal | verified_after_retry | 1 | NSSAI is a collection of S-NSSAIs used for slice selection |
| 7 | adversarial | verified_after_retry | 2 | "the text does not describe the MME's interaction with the UDM or HSS" |
| 8 | adversarial | verified_after_retry | 3 | "the AMF does not exist in EPS" |
| 9 | adversarial | verified_after_retry | 2 | EPS bearer identity is not part of 5G registration |
| 10 | adversarial | verified_after_retry | 2 | "the SMF does not connect to the SGW for user plane traffic" |
| 11 | adversarial | verified_after_retry | 3 | "the PDN Gateway belongs to 4G EPS" |
| 12 | adversarial | verified_after_retry | 2 | "there is no 5G Session Management Tracking Area Update message" |

## Why the numbers can't be trusted

- **Every row is "verified_after_retry".** The verifier counted its own first check as a retry (the off-by-one bug, plan finding #1), so a first-pass success recorded `retries: 1`. The "100% verified" reading is an artifact of that.
- **Incomplete run.** It stopped after 12 of 18 questions and never tested refusals.
- **Leaks.** Several answers say "Based on the provided specifications", which the pipeline is meant to hide.
- **Different setup.** Written before the clause-tree fixes, before bulleted lists were indexed (about 37% of the spec text was missing) and with the old reranker. The model isn't recorded in the file; `.env.example` at the time pointed at a larger model (`qwen/qwen3.6-27b` via Groq), while today's runs use `openai/gpt-oss-20b` via OpenRouter.

The first trustworthy before/after numbers are the frozen baseline in `eval/baseline/` (2026-10-01) and the runs under `eval/runs/`.
