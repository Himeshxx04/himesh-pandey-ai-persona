# Himesh Pandey — AI Persona

> Voice + chat AI representative of [Himesh Pandey](https://github.com/Himeshxx04). Talk to it about my projects, my background, or book a real interview slot on my Cal.com calendar — end to end, no human in the loop. Submission for the SCALER AI Engineer screening.

**Live now:**
- 💬 **Chat:** https://himesh-pandey-ai-persona.vercel.app
- 📞 **Phone:** +1 (937) 888-3660 *(US number — international rates apply)*
- 🌐 **Browser call:** click "Call this agent" on the chat page
- 📂 **Repo:** https://github.com/Himeshxx04/himesh-pandey-ai-persona

---

## What it does

| Capability | How |
|---|---|
| Answers "why are you right for this role" | RAG over my resume + about_me + my two flagship GitHub repos (READMEs + commit history) |
| Repo deep-dives (tradeoffs, what you'd change) | Same RAG corpus — questions only answerable from my READMEs land correctly |
| Books a real meeting | Cal.com v2 API — slots fetched live, booking creates a real calendar invite with a Cal Video link |
| Resists prompt injection | System prompt + retrieval guard return zero context for off-topic queries, so the LLM has nothing to comply with |
| Doesn't hallucinate bookings | Code-level guard in `brain.py` re-runs the tool loop if the model claims success without `book_slot` actually firing |
| Voice barge-in / interruptions | LiveKit Agents + Silero VAD + ML turn-detector |

---

## Architecture

```
                            ┌─────────────────────────────────────┐
                            │   corpus/                           │
                            │     resume.pdf                      │
                            │     about_me.md                     │
                            │     github/                         │
                            │       rag-pipeline-optimizer/       │
                            │       mcp-artifact-store/           │
                            │       (READMEs + git log + docs)    │
                            └────────────────┬────────────────────┘
                                             │
                                             ▼
                            ┌─────────────────────────────────────┐
                            │   persona/  (shared brain)          │
                            │                                     │
                            │     ingest.py  → FAISS (CPU)        │
                            │     retriever.py (multi-qa-MiniLM)  │
                            │     prompts.py (guardrails)         │
                            │     llm.py (provider-agnostic)      │
                            │     brain.py (hallucination guard)  │
                            │     tools/booking.py (Cal.com v2)   │
                            └──┬───────────────────────────────┬──┘
                               │                               │
              imported by      │                               │      imported by
       ┌───────────────────────┘                               └──────────────────────┐
       ▼                                                                              ▼
┌──────────────────────┐                                          ┌────────────────────────────────┐
│  api/main.py         │                                          │  voice/agent.py                │
│  FastAPI             │                                          │  LiveKit Agents 1.5 (Python)   │
│  POST /ask           │                                          │                                │
│  POST /ask/stream    │                                          │  ┌──────────────────────────┐  │
│  POST /voice/token   │                                          │  │ Deepgram Nova-3 (STT)    │  │
│  POST /voice/callback│                                          │  │ OpenAI gpt-4o-mini (LLM) │  │
│  GET  /health        │                                          │  │ ElevenLabs Flash v2.5    │  │
│                      │                                          │  │   (Brian voice, TTS)     │  │
│  Render Standard 2GB │                                          │  │ Silero VAD + ML turn-    │  │
│  Always-on           │                                          │  │   detector for barge-in  │  │
└──────────┬───────────┘                                          │  └──────────────────────────┘  │
           │                                                      │                                │
           ▼                                                      │  Render Standard 2GB           │
┌──────────────────────┐                                          │  Always-on                     │
│  frontend/           │                                          └──────────────┬─────────────────┘
│  React + Vite + TW   │                                                         │
│  Vercel              │                                                         │
│                      │  ◄── browser WebRTC ─────────────────────────────────► LiveKit Cloud
│  ChatPanel (SSE)     │                                                                 ▲
│  CallButton          │                                                                 │
│  PhoneFallback       │                                                                 │
└──────────────────────┘                          ┌──────────┐                            │
                                                  │ Twilio   │ ──── SIP trunk ────────────┘
                                                  │ +1 (937) │
                                                  │ 888-3660 │
                                                  └────▲─────┘
                                                       │ PSTN
                                                       │
                                                  [Caller]
```

**Key design: "one brain, two channels."** The `persona/` package is imported in-process by both the chat backend and the voice worker. No HTTP hop between the voice agent and the retriever — RAG runs synchronously inside the LiveKit turn lifecycle (`on_user_turn_completed`). Same prompts, same retriever, same booking tool everywhere. Adding a third channel (Slack, WhatsApp) is a single import.

---

## Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| Embeddings | `multi-qa-MiniLM-L6-cos-v1` | Asymmetric Q→doc model. The initial `all-MiniLM-L6-v2` scored question phrasings 0.15 against the matching chunk; this one scores 0.78 on the same query/chunk pair. |
| Vector store | FAISS CPU (in-process) | Corpus is ~140 chunks. No external service worth the latency tax. |
| Chat LLM | OpenAI `gpt-4o-mini` | Cheapest model that handles function calling reliably for the booking tool. |
| Voice STT | Deepgram Nova-3 streaming, `language="multi"` | ~200ms transcript delay; multi-language picks up Hindi/Hinglish without config. |
| Voice TTS | ElevenLabs Flash v2.5, "Brian" voice | ~75ms first byte; deep professional male voice. |
| Voice orchestration | LiveKit Agents 1.5 | Real barge-in handling, SIP support, ML turn-detector plugin. |
| Telephony | Twilio US number → SIP → LiveKit | Twilio can't provision +91 numbers in time; US works for evaluators. |
| Calendar | Cal.com v2 API | Free tier, clean REST API, real booking + Cal Video link generation. |
| Chat backend | FastAPI + uvicorn | Async, supports SSE for streaming chat. |
| Frontend | React + Vite + Tailwind | Fast build, minimal bundle. |
| Hosting | Render Standard ($25/mo × 2) + Vercel Hobby | Always-on for 7-day eval window. No cold starts. |

---

## Hard problems I solved

These are the issues an evaluator might probe — explained from root cause to fix.

### 1. Chat hallucinated booking confirmations

**Symptom:** Even with a strict system prompt saying "never claim a booking unless `book_slot` returned a result", `gpt-4o-mini` would narrate "I've confirmed the slot for Tuesday at 3 PM, you'll receive an email shortly" without ever calling the tool.

**Root cause:** Two issues stacked. (a) `is_booking_intent()` only checked the current user message for keywords. When the user replied with just "Name + email", the message had no booking keyword, so the request was routed to the streaming path which has no tools attached, and the LLM just kept narrating. (b) Even when tools were available, the model would sometimes skip the tool call and synthesize a fake confirmation.

**Fix:** (a) `is_booking_intent()` now also inspects the *most recent assistant turn* — if I just asked for name/email, the user's reply is treated as part of the booking flow regardless of keyword match. (b) Added a code-level hallucination guard in `brain.answer()`: if the response text contains booking-confirmation phrases AND `book_slot` was never actually invoked, the conversation is replayed with a system-correction message telling the LLM to either call `book_slot` for real or honestly ask for what's missing.

### 2. Voice first-turn latency was 13s, not <2s

**Symptom:** Phone-call test logs showed 13s between the caller finishing their first sentence and the agent's response starting. Subsequent turns were fast.

**Root cause:** The FAISS retriever was lazy-loaded inside `on_user_turn_completed` on the first user turn. Loading sentence-transformers + FAISS pinned ~2-3s of CPU. That CPU spike starved Silero VAD, which fell behind realtime, which made Deepgram's streaming WebSocket hit its 10s no-audio timeout and reconnect — adding 10s. The 13s was 3s of model load + 10s of Deepgram reconnect.

**Fix:** In `entrypoint()`, kick off the retriever load on a background thread the moment the call connects. By the time the caller finishes their first sentence (5-10s of speech + silence detection), the retriever is warm. The CPU spike happens in parallel with call setup, hidden behind the user talking. Latency dropped from 13s to ~1.5s.

### 3. Voice booking sent past dates to Cal.com

**Symptom:** Booking calls over voice would 400 from Cal.com with no useful error.

**Root cause:** When the LLM had a stale conversation context, it would sometimes construct a `start_utc` argument from training data ("2023-06-08T...") instead of copying verbatim from the `check_availability` result.

**Fix:** Added a past-date guard in `BookingTool.book_slot()` that rejects any `start_utc` before `now()`. The voice agent catches the resulting `ValueError` and asks the LLM to re-check availability. Also strengthened the tool description to say "the `start_utc` MUST be an exact `utc_ref` from `check_availability`, never construct one yourself" — between the code guard and the description, hallucinated dates stopped reaching Cal.com.

### 4. Slot listings stuck on one day

**Symptom:** When asked "what about next Wednesday?", agent said no availability — even though Wednesday had open slots.

**Root cause:** `_fetch_slots()` returned `slots[:8]`. If today (Monday) had 8+ open slots, the [:8] cap consumed the entire budget, and Tuesday onwards never reached the LLM.

**Fix:** Group Cal.com response by date, take first 2 slots per day, cap at 12 total. LLM always sees variety across 5-6 different days. Plus a `_filter_slots_by_hint()` that parses "tomorrow", day names, "jun 10", etc. and narrows the slot list so the LLM can answer "are you free Wednesday?" precisely.

---

## Cost breakdown

### Per-chat session (one /ask request)

| Item | Cost |
|---|---|
| FAISS retrieval (sentence-transformers, local CPU) | $0 |
| Embedding call | $0 (local) |
| OpenAI gpt-4o-mini: ~700 input tokens (system + context + history) + ~200 output | **~$0.00026** |
| If booking flow (2 round-trips through tool loop): ~1400 in + 300 out | **~$0.00050** |
| Cal.com API calls | $0 (free tier) |
| **Typical chat answer:** | **~$0.0003 (≈ ₹0.025)** |
| **Booking chat session:** | **~$0.0010 (≈ ₹0.08)** |

### Per voice call (5-minute call, typical)

| Item | Estimate | Cost |
|---|---|---|
| Twilio inbound (US, 5 min @ $0.0085/min) | 5 min | $0.043 |
| LiveKit Cloud per-participant minute | 5 min @ $0.005 | $0.025 |
| Deepgram Nova-3 streaming STT | 5 min @ $0.0043/min | $0.022 |
| ElevenLabs Flash v2.5 TTS (~2,000 chars) | 2k chars | $0.066 |
| OpenAI gpt-4o-mini (LLM, multi-turn) | ~3k in + 500 out | $0.0007 |
| **Per 5-min call:** | | **~$0.16 (≈ ₹13.50)** |

### Hosting (7-day eval window)

| Service | Plan | 7-day prorated |
|---|---|---|
| Render API (himesh-persona-api) | Standard 2GB | ~$5.83 |
| Render voice worker (himesh-persona-voice) | Standard 2GB | ~$5.83 |
| Vercel frontend | Hobby | $0 |
| Cal.com | Free | $0 |
| **Total hosting:** | | **~$11.66 for 7 days** |

---

## Repo structure

```
.
├── corpus/                  # resume, about_me, cloned GitHub READMEs+git log
├── persona/                 # shared brain — imported by chat AND voice
│   ├── ingest.py            #   load corpus → FAISS index
│   ├── retriever.py         #   FAISS top-k, source-tagged chunks
│   ├── prompts.py           #   system prompt + guardrails
│   ├── llm.py               #   provider-agnostic + function calling
│   ├── brain.py             #   Brain class + hallucination guard
│   └── tools/booking.py     #   Cal.com v2 integration
├── api/main.py              # FastAPI: /ask, /ask/stream, /voice/token, /voice/callback
├── voice/agent.py           # LiveKit Agents worker
├── frontend/                # React + Vite + Tailwind
├── data/golden_qa.jsonl     # 10 grounded Q&A pairs for eval
├── evals/                   # eval harness
├── scripts/ingest_github.py # clones the two flagship repos, extracts README + git log
├── render.yaml              # both services + plan + env config
├── requirements.txt
└── docs/assignment.pdf
```

---

## Run it locally

```bash
# 1. Setup
python -m venv venv && venv\Scripts\activate            # Windows
pip install -r requirements.txt

# 2. .env
cp .env.example .env                                     # then fill in keys

# 3. Ingest corpus (one-time, or after corpus changes)
python scripts/ingest_github.py
python -c "from persona.ingest import build_index; build_index(force=True)"

# 4. Run
uvicorn api.main:app --reload --port 8000                # chat backend
python voice/agent.py dev                                # voice worker (separate terminal)
cd frontend && npm install && npm run dev                # frontend (separate terminal)
```

See `voice/README.md` for the LiveKit + Twilio SIP wiring playbook.

---

## What I'd build with two more weeks

- **Real eval harness in CI:** golden_qa.jsonl runs every PR through an LLM judge for hallucination + a precision/recall check on retrieval sources. Block merges that regress.
- **Long-tail call quality:** add a small "intent classifier" before the LLM so off-script questions ("what's your favorite movie") get routed to a one-shot rejection instead of through the full RAG stack.
- **Multi-tenant version:** generalize `corpus/` and `persona/prompts.py` so any candidate can clone the repo, drop in their own resume + repos, and have a working AI persona in <10 minutes. Sell as a SaaS to job-seekers.
- **Memory across calls:** Cal.com knows who booked. Surface "you spoke to me last Tuesday — want to follow up on the MCP discussion?" on the next call.

---

## Contact

— Himesh Pandey · pandeyhimesh09@gmail.com · [GitHub](https://github.com/Himeshxx04) · [LinkedIn](https://www.linkedin.com/in/himesh-pandey-66968a213/)
