# Phase 7 — public demo: working decisions

A running log for Phase 7 (#59). Decisions here are provisional until the phase ships; settled ones move to `DECISIONS.md` at the end.
Status legend: **Decided** (agreed with the owner) · **Proposed** (awaiting approval) · **Open** (needs an answer).

## Requirements (Decided)

- Public website, no login.
- The project must last long on a small LLM credit balance (~$5 on OpenRouter).
- **5 questions per visitor per day.**
- When the global budget is used up, the site **tells the visitor** and stops answering new questions. No "bring your own key".
- **Hosting is free.** Paid only if a hard constraint forces it.

## High-level design (Proposed)

```
 Browser
   │  loads static site (always on, instant)
   ▼
 Frontend: SvelteKit static build ── Cloudflare Pages (free)
   │  HTTPS calls to the API, visitor token in a request header
   ▼
 Backend: FastAPI ── one Docker container on Modal (free Starter plan, $30 usage/month; 2 CPU, 2 GB)
   ├─ Quota gate ──────────────► Upstash Redis (free): per-visitor daily counters
   ├─ LangGraph graph (unchanged): cache → triage → retrieve → generate
   │     ├─ Qdrant Cloud free cluster (search over the 6,124 points)
   │     ├─ BGE embedder + Ettin reranker, baked into the image
   │     └─ generate ─────────► OpenRouter (gpt-oss-20b), provider-side spend limit
   └─ Charge quota only if the question reached the LLM
```

### Concern 1: Hosting

| Piece | Where | Why |
|---|---|---|
| Backend + models | **Modal**, free Starter plan (Decided) | The app needs ~840 MB RAM; every no-card free host checked gives ≤512 MB (Render, Railway, Koyeb, Northflank), Hugging Face Docker Spaces now need PRO, Vercel/Netlify only run tiny functions. Modal bills per second only while running ($30/month free); at ~$0.002 per visit that's thousands of visits, far beyond the OpenRouter budget. Deployed by `deploy/modal_app.py` from the same Dockerfile. Limits: 1 container, sleeps after 5 idle minutes. |
| Qdrant points | **Qdrant Cloud free cluster** (Decided) | 1 GB RAM, 4 GB disk; our index (~10 MB vectors + ~20 MB payload) fits easily. Loaded with `deploy/copy_qdrant.py`, which copies points with their stored vectors (no re-embedding). Chosen over a snapshot because a snapshot must match the cloud's Qdrant version; a point copy works across versions. |
| Frontend | Cloudflare Pages | Static files, free, never sleeps, so the page loads instantly and can say "waking the server up" while the backend starts. |
| Counters | Upstash Redis free tier | The container's disk is wiped whenever it sleeps, so counters must live outside it. Redis has atomic counters with automatic expiry, which fits "per day" exactly. |

Known behaviour (measured): after 5 idle minutes the backend sleeps; the next visitor waits ~20–26 s (model load ~16 s). Warm replies to health/quota take ~1 s. The frontend shows a "waking up" state for that. Image needs ~840 MB RAM.

**Qdrant Cloud free tier rules and how we handle them:**
- An unused free cluster is **suspended after 1 week and deleted after 4 weeks**. Fix: a free scheduled GitHub Actions job runs one real search against it every few days, so it never counts as idle.
- If it is ever deleted anyway: re-run `deploy/copy_qdrant.py` from the local Qdrant (seconds, not a 25-minute re-index).
- Code change needed: the retriever connects with a URL only; it needs a `qdrant_api_key` setting (empty locally, set on the host).
- Create the cluster in the same region as the backend host to keep search latency low.

### Concern 2: Budget protection

**Built 2026-11-11** (`src/api/quota.py`, tests in `tests/test_api.py`): per-visitor and per-IP daily limits on Upstash Redis (REST), charged only when the LLM was reached. Checked live: off-topic questions leave the counter untouched. Details below; deviations from the plan are noted inline.

- **Visitor identity:** a server-signed visitor token stored in the browser, plus the IP address (IPv6 → /64 prefix). A cookie won't work, because the frontend and backend are on different domains and browsers block such cookies. The token goes in a request header instead.
- **Per-visitor limit:** 5 LLM-reaching questions per day per token (UTC day). Per IP the limit is higher (15/day; a request without a valid token gets 5/day on its IP), so people sharing one network (college, office) aren't blocked by each other, but clearing storage to get a new token only buys a few extra questions.
- **Global limit (Decided):** no separate daily cap. The global budget is the OpenRouter credit balance. When it runs out, OpenRouter rejects the call (HTTP 402) and the site tells the visitor the demo budget is used up. The remaining balance can be read from OpenRouter's key endpoint for the quota panel. ($5 ≈ 1,470 answered questions at ~$0.0034 each.)
- **What counts:** only questions that reach the LLM. Off-topic refusals (triage) and cache hits are free.
- **Fail-open:** if Redis can't be reached, questions are allowed and logged; the OpenRouter key's credit limit is the backstop.
- **Race-safe:** the limit is re-checked inside the one-at-a-time graph lock, so parallel requests can't slip past it.
- **Exhausted:** a clear message (per-visitor: come back tomorrow; global: demo budget used up). Example questions stay clickable (their answers are pre-computed and served free).
- **Last line of defence:** a credit limit on the OpenRouter API key (set by the owner in the OpenRouter dashboard).
- **Model (Decided):** one model, the paid `openai/gpt-oss-20b` the benchmarks used. No free-variant fallback. A model dropdown may be added later if wanted.

### Concern 3: Frontend

SvelteKit, built as static files. Svelte components work like React components: one `.svelte` file holds the markup, logic and styles, and takes props.

```
App
├─ Header (Ask · About)
├─ Banner (server waking up / budget used up)
├─ AskPage
│  ├─ ExampleQuestions (pre-computed, free)
│  ├─ MessageList
│  │  ├─ UserMessage
│  │  └─ AnswerMessage
│  │     ├─ StatusBadge (answered / partial / not covered / refused)
│  │     ├─ PipelineSteps (live: checking → searching → answering)
│  │     └─ SourceList → SourceCard (spec, clause, title, excerpt)
│  ├─ QuotaPanel (your questions left today · demo budget left)
│  └─ Composer (input + send; disabled when quota is 0)
└─ AboutPage (what it does, architecture, measured results)
```

Shared state (conversation, quota) lives in Svelte stores.

### Frontend (planning; no drafting until the owner gives the green flag)

The component tree above was an early sketch; the decisions below replace it.

All Decided (owner, 2026-11-11). Built in `frontend/` (see "Frontend build" below).

- **Purpose:** the frontend pitches the product, not just a chat box. **Audience:** telecom engineers first; the engineering underneath should impress hiring managers.
- **Look:** light theme; Inter for text, JetBrains Mono for 3GPP identifiers; one accent colour.
- **Page:** one page, four sections: 1 Pitch → 2 Pipeline → 3 Evals → 4 Demo.
  1. **Pitch:** headline, the problem (shared vocabulary, e.g. GUTI ≠ 5G-GUTI), who it is for, 4 strong number tiles worded exactly as measured ("0 made-up answers on 11 questions the specs don't cover", never "never hallucinates").
  2. **Pipeline:** detailed interactive diagram, two lanes (built once / every question). Ingestion is one block whose detail lists its key design choices. Click a step for what / why / one measured number.
  3. **Evals:** test set (40 questions by type), release criteria across both runs including the miss, search quality 15 → 17 → 20 of 29, known limits, tried and dropped. No per-question browser, no grading-method details.
  4. **Demo:** visitor-driven chat. A simple vertical flow in a side panel animates live per question; few steps, each showing one real fact from that run. Each answer keeps its flow (click an older answer to see it). On phones the panel is a drawer.
- **Live animation:** real streaming: one event per finished node over Server-Sent Events (`POST /api/ask/stream`). No extra LLM cost.
- **Examples:** 4 buttons (normal Q1, 4G/5G trap Q7, off-topic Q16, spec + clause). They replay a recorded run, labelled as such, once recorded; until then they run live.
- **Tours:** automatic, each shown once per browser and skippable: pipeline, evals, demo, and after the first answer. Footer link replays them.
- **Cold start:** the page calls `/api/health` on load so the server wakes while the visitor reads.

### Frontend build — v1 shipped (2026-11-11)

**Status: v1 accepted by the owner for shipping; more enhancements to follow.** Verified section by section in a live Chrome window.

What v1 contains, beyond the plan above (owner's first-pass review):
- **Pipeline** is a full system map (draw.io style), not sequential blocks: Ingestion and Serving groups, a LangGraph group and an Observability row; decision diamonds for every branch with their end states; dotted edges for build artefacts used at query time (lexicon, centroids, clause index, Qdrant vectors); sticky notes for edge cases; tech on every box (Docling, FastEmbed/BGE-small, Qdrant Cloud, SQLite, Ettin reranker, OpenRouter gpt-oss-20b, FastAPI on Modal, SvelteKit on Cloudflare Pages, structlog/Langfuse/RunRecorder). Hover traces a box's edges; click opens its detail.
- **Demo** is a dark, chatbot-style window: header (server status, budget, New chat), ChatGPT-style suggestion cards on the empty chat, message bubbles, pill input.
- **Evals:** the "wrong answers labelled answered" row removed (owner); "Met, no margin" renamed "Met · at the limit" with an explanation.
- **Author:** name and GitHub in the hero and a four-column footer.

Known follow-ups: LinkedIn URL (empty slot in `site.ts`); the page shifts ~100 px when a question is sent; the live route has not yet been watched at real speed (needs one in-scope question); example recordings not made yet.

SvelteKit 3 (Svelte 5), static build for Cloudflare Pages, Driver.js for tours. Built for customisation: components contain no copy or numbers.

| Change | Edit |
|---|---|
| Section order, nav links, backend URL | `frontend/src/lib/config/site.ts` (`VITE_API_BASE` in `frontend/.env`) |
| Any text or number in a section | `frontend/src/lib/content/{pitch,pipeline,evals,demo}.ts` |
| System map: boxes, positions, arrows, groups | `content/pipeline.ts` (fixed 1600 × 1300 canvas, scaled to fit; routing in `lib/map.ts`) |
| Author, footer links | `config/site.ts` (`author`, `footer`) |
| Live-panel steps and their fact lines | `content/demo.ts` → `flow.steps` (maps backend nodes to steps) |
| Tours | `content/tours.ts` (`target` = a `data-tour` attribute) |
| Colours, type, spacing | `frontend/src/lib/theme/tokens.css` |
| Add a section | a component in `components/sections/`, one line in `registry.ts`, its id in `site.ts` |

Example recordings: `npm run record` (in `frontend/`, backend running) writes `content/recordings.json`. Spends one LLM call per in-scope example.

### Concern 4: Backend API

- `POST /api/ask`: run graph → answer, status, sources (JSON).
- `POST /api/ask/stream`: the same run as Server-Sent Events: `start`, one `node` event per finished node with its time and facts (`src/api/events.py`), then `done` (the answer) or `error` (out of OpenRouter credit → `budget_exhausted`).
- Both: quota check and charge arrive in step 5. `/api/ask` answers out of credit (HTTP 402) with 503 `budget_exhausted`.
- `GET /api/quota`: OpenRouter balance (`/api/v1/credits`, cached 60 s); per-visitor part arrives in step 5.
- `GET /api/health`: liveness check for the host and the frontend's "waking up" check.

The graph, retrieval and prompts are not changed by Phase 7.

## Approach

Build a thin end-to-end slice first, deployed, then thicken it. The biggest risk is "does it run on free hosting", so that is tested first.

1. **Qdrant Cloud** — done.
2. **Backend API** — done.
3. **Hosting check** on Modal — done.
4. **Frontend** — v1 built and accepted (2026-11-11), not deployed yet. Superseded the "minimal first" plan.
5. **Budget protection** — built (2026-11-11). Needs the Modal redeploy to be live.
6. **Frontend enhancements** after launch prep.
7. **Launch:** share the link, Qdrant keep-alive job, runbook, remove Streamlit.

## Log

- 2026-11-09 — Requirements recorded (5/day per visitor, notify on global exhaustion, free hosting). HLD proposed.
- 2026-11-09 — Qdrant Cloud free tier chosen for the points. One model (paid gpt-oss-20b), no free-variant fallback; dropdown possibly later.
- 2026-11-09 — Sprint 1 (steps 1–3) built: `qdrant_api_key` setting, `deploy/copy_qdrant.py`, `src/api/main.py` + tests, `Dockerfile`, `deploy/push_space.py`. Questions are served one at a time (lock around the graph), matching a 2-vCPU host.
- 2026-11-09 — Step 1 done: 6,124 points copied to Qdrant Cloud (us-west-1) with keyword indexes on `spec_id`/`clause_id` (Cloud refuses unindexed filters). Retrieval report against Cloud identical to local: answer chunk in top 5 20/29.
- 2026-11-09 — **Blocker:** Hugging Face no longer hosts Docker Spaces on free CPU without a PRO subscription (402 on Space creation). Backend host to be re-chosen. Measured image needs: ~730 MB RAM, 3.1 GB image, 17 s model load — rules out 512 MB free tiers (Render, Koyeb).
- 2026-11-09 — No global daily cap: the OpenRouter balance is the global budget; notify when it runs out.
- 2026-11-09 — Backend host: **Modal** (free Starter plan). `deploy/modal_app.py` deploys the Dockerfile; secrets go into the named Modal secret `3gpp-echo-api-env` from `.env`; `modal run deploy/modal_app.py::check` smoke-tests Qdrant + OpenRouter from inside the container (no tokens). Live at `https://csrosex--3gpp-echo-api-api.us-east.modal.run`: health, quota ($4.80) and an off-topic refusal verified; cold start 20–26 s. HF deploy files removed. Steps 1–3 done.
- 2026-11-11 — Budget protection built: visitor token (`X-Visitor-Token`, HMAC-signed), 5/day per visitor, 15/day per IP (/64 for IPv6), Upstash Redis over REST, charge only LLM-reaching answers, fail-open; frontend shows "N of 5 questions left today" and disables typing at 0 (recorded examples still play).
- 2026-11-11 — Frontend v1 accepted for shipping after the owner's first-pass review (system map, dark chatbot demo, footer and author, evals edits).
- 2026-11-11 — Frontend built (local, not deployed): four sections, live route panel over SSE, tours; `POST /api/ask/stream` added with tests. Frontend planning started earlier that day.
- 2026-11-11 — Frontend planning started. Decided: pitch-first purpose, light theme, heavy guided tours, one page with three sections (pitch → interactive pipeline diagram → visitor-driven demo with a live vertical node flow in a side panel). No drafting until the owner's green flag.
