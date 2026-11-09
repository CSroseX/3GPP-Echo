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

- **Visitor identity:** a server-signed visitor token stored in the browser, plus the IP address (IPv6 → /64 prefix). A cookie won't work, because the frontend and backend are on different domains and browsers block such cookies. The token goes in a request header instead.
- **Per-visitor limit:** 5 LLM-reaching questions per day per token. Per IP the limit is higher (e.g. 15/day), so people sharing one network (college, office) aren't blocked by each other, but clearing storage to get a new token only buys a few extra questions.
- **Global limit (Decided):** no separate daily cap. The global budget is the OpenRouter credit balance. When it runs out, OpenRouter rejects the call (HTTP 402) and the site tells the visitor the demo budget is used up. The remaining balance can be read from OpenRouter's key endpoint for the quota panel. ($5 ≈ 1,470 answered questions at ~$0.0034 each.)
- **What counts:** only questions that reach the LLM. Off-topic refusals (triage) and cache hits are free.
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

### Concern 4: Backend API

- `POST /api/ask`: run graph → answer, status, sources (JSON, not streamed yet; streaming the pipeline steps can come with the full frontend). Quota check and charge arrive in step 5. Out of OpenRouter credit (HTTP 402) → 503 `budget_exhausted`.
- `GET /api/quota`: OpenRouter balance (`/api/v1/credits`, cached 60 s); per-visitor part arrives in step 5.
- `GET /api/health`: liveness check for the host and the frontend's "waking up" check.

The graph, retrieval and prompts are not changed by Phase 7.

## Approach

Build a thin end-to-end slice first, deployed, then thicken it. The biggest risk is "does it run on free hosting", so that is tested first.

1. **Qdrant Cloud** — done.
2. **Backend API** — done.
3. **Hosting check** on Modal — done.
4. **Minimal frontend** on Cloudflare Pages calling it: one input, one answer. Not shared publicly yet.
5. **Budget protection** before the link is shared anywhere.
6. **Full frontend:** components above, About page.
7. **Launch:** share the link, Qdrant keep-alive job, runbook, remove Streamlit.

## Log

- 2026-11-09 — Requirements recorded (5/day per visitor, notify on global exhaustion, free hosting). HLD proposed.
- 2026-11-09 — Qdrant Cloud free tier chosen for the points. One model (paid gpt-oss-20b), no free-variant fallback; dropdown possibly later.
- 2026-11-09 — Sprint 1 (steps 1–3) built: `qdrant_api_key` setting, `deploy/copy_qdrant.py`, `src/api/main.py` + tests, `Dockerfile`, `deploy/push_space.py`. Questions are served one at a time (lock around the graph), matching a 2-vCPU host.
- 2026-11-09 — Step 1 done: 6,124 points copied to Qdrant Cloud (us-west-1) with keyword indexes on `spec_id`/`clause_id` (Cloud refuses unindexed filters). Retrieval report against Cloud identical to local: answer chunk in top 5 20/29.
- 2026-11-09 — **Blocker:** Hugging Face no longer hosts Docker Spaces on free CPU without a PRO subscription (402 on Space creation). Backend host to be re-chosen. Measured image needs: ~730 MB RAM, 3.1 GB image, 17 s model load — rules out 512 MB free tiers (Render, Koyeb).
- 2026-11-09 — No global daily cap: the OpenRouter balance is the global budget; notify when it runs out.
- 2026-11-09 — Backend host: **Modal** (free Starter plan). `deploy/modal_app.py` deploys the Dockerfile; secrets go into the named Modal secret `3gpp-echo-api-env` from `.env`; `modal run deploy/modal_app.py::check` smoke-tests Qdrant + OpenRouter from inside the container (no tokens). Live at `https://csrosex--3gpp-echo-api-api.us-east.modal.run`: health, quota ($4.80) and an off-topic refusal verified; cold start 20–26 s. HF deploy files removed. Steps 1–3 done.
