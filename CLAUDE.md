# SCALER AI Engineer Screening — Himesh Pandey Persona

**Deadline: June 6 2026, 7:30 PM IST. ~36 hours from project start.**
Full assignment: `docs/assignment.pdf`

---

## RESUME PROTOCOL (fresh session entry point)

You are the pair-engineer for this project. Read this file top to bottom, find the first unchecked `[ ]` task in BUILD PHASES, and continue from there. The repo + this file = complete state. No re-explanation needed — just pick up and build.

---

## Assignment Requirements Checklist

Hard requirements from `docs/assignment.pdf`:

- [ ] **Voice agent** — callable phone number (US +1 via Twilio); <2s first response; handles barge-in/interruptions; introduces itself as Himesh's AI rep; answers background/skills questions; asks for availability, checks real calendar, proposes slots, books confirmed meeting without human in loop
- [ ] **Chat interface** — public URL; RAG-grounded (resume + GitHub repos, NO hardcoded strings); answers fit-for-role, repo deep-dives, resume questions; books calls; resists adversarial/injection probing; stays honest (say "I don't know", never invent)
- [ ] **Real calendar booking** — actual availability + confirmation via Cal.com (or Calendly / Google Cal)
- [ ] **RAG grounded** — reads real resume.pdf + about_me.md + GitHub repo READMEs + commit history; FAISS local index; no hardcoded Q&A
- [ ] **Voice latency** — <2s first response measured end-to-end; barge-in handled without crash
- [ ] **Public GitHub repo** — clean README, architecture diagram, setup instructions, cost breakdown (per call / per chat session)
- [ ] **Eval report** — 1-page PDF: voice latency / transcription accuracy / booking success rate; hallucination rate + how measured; retrieval precision/recall; 3 failure modes + root cause + fix; 1 conscious tradeoff; what you'd build with 2 more weeks
- [ ] **Loom walkthrough** — ≤4 min (hard req table); ≤3 min (submission form) — target ≤3 min to be safe; architecture + 1 hard problem solved
- [ ] **Live 7 days** after submission; Scaler will call/chat unannounced

Submission form: https://forms.gle/MrZMGCKikHaFkA3J9
Fields: name+email, phone number, chat URL, GitHub link, eval PDF, Loom link, build time

---

## Locked Architecture & WHY

### "One brain, two channels"

```
corpus/ (resume + about_me + GitHub READMEs + git log)
  └─→ persona/ package  ←─ imported by BOTH channels
        ├── ingest.py       corpus → FAISS index (sentence-transformers, local $0)
        ├── retriever.py    FAISS top-k retrieval + source metadata
        ├── prompts.py      system prompt + guardrails (honesty, injection resistance)
        ├── llm.py          provider-agnostic wrapper (OpenAI / Anthropic / Groq)
        ├── brain.py        Brain class: retrieve → prompt → LLM → answer + sources
        └── tools/
            └── booking.py  Cal.com tool (check_availability + book_slot)

api/main.py          FastAPI: POST /ask  →  chat channel
voice/agent.py       LiveKit agent       →  voice channel  [Phase 3]
frontend/            React chat UI                         [Phase 4]
```

WHY one shared package: latency and consistency. The voice agent can call `brain.answer()` directly in-process without an HTTP hop. Both channels produce identical grounded answers from the same retriever + prompts.

### Voice Stack

```
Caller → Twilio US number (+1) → SIP trunk → LiveKit Cloud
  → LiveKit Agents SDK (Python)
    → Deepgram STT (Nova-2, streaming)
    → Brain.answer() [imported persona/]
    → ElevenLabs TTS (Flash v2.5, ~75ms)
  → LiveKit → Twilio → Caller
```

WHY Twilio US (+1): Twilio cannot provision Indian (+91) numbers fast enough for a 48h build. US number works fine for Scaler's evaluators.
WHY LiveKit Agents: handles barge-in and turn-taking natively; Python SDK fits our stack.
WHY Deepgram Nova-2: lowest STT latency among supported providers.
WHY ElevenLabs Flash v2.5: ~75ms streaming TTS, natural voice.

### Calendar Booking
Cal.com free tier. Exposed as a tool to both brain channels. `check_availability(date_range)` + `book_slot(slot, attendee_info)` → Cal.com REST API.

---

## Tech Stack & Rationale

| Layer | Choice | Why |
|---|---|---|
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` | Local, $0, 80MB, good quality for small corpus |
| Vector store | FAISS (CPU) | Local, no external service, corpus ~15k tokens total |
| LLM | OpenAI gpt-4o-mini (default) | Cheapest capable model; swap via .env |
| Voice STT | Deepgram Nova-2 | Lowest latency, accurate |
| Voice TTS | ElevenLabs Flash v2.5 | ~75ms, natural |
| Voice orchestration | LiveKit Agents (Python) | Barge-in, turn-taking, SIP |
| Telephony | Twilio (US +1) | SIP → LiveKit, reliable |
| Calendar | Cal.com | Free tier, clean API, real booking |
| Chat backend | FastAPI + uvicorn | Async, fast, our core stack |
| Chat frontend | React + Vite + Tailwind | Minimal modern UI |
| Deployment | Render (FastAPI) + Vercel (React) | Fast deploy, free tier |

---

## Repo Structure

```
scaler-persona/
├── docs/assignment.pdf          # SOURCE OF TRUTH — never edit
├── corpus/
│   ├── resume.pdf               # Himesh's resume (gitignored)
│   ├── about_me.md              # First-person grounding (gitignored)
│   └── github/                  # Cloned READMEs + git logs (auto-generated)
├── persona/
│   ├── __init__.py
│   ├── ingest.py                # Load corpus → chunks → FAISS index
│   ├── retriever.py             # FAISS retriever, returns chunks + source
│   ├── prompts.py               # System prompt + guardrail instructions
│   ├── llm.py                   # Provider-agnostic LLM (OpenAI/Anthropic/Groq)
│   ├── brain.py                 # Brain(retriever, llm, tools) → answer(msg, history)
│   └── tools/
│       ├── __init__.py
│       └── booking.py           # Cal.com tool (stub → real in Phase 2)
├── api/
│   ├── __init__.py
│   └── main.py                  # FastAPI POST /ask, GET /health
├── voice/
│   └── agent.py                 # LiveKit agent [Phase 3]
├── frontend/                    # React chat UI [Phase 4]
├── data/
│   └── golden_qa.jsonl          # Golden Q&A for eval
├── evals/
│   └── run_evals.py             # Eval harness [Phase 5]
├── scripts/
│   └── ingest_github.py         # Clone repos + extract READMEs + git log
├── .env.example
├── .gitignore
├── CLAUDE.md                    # THIS FILE
├── requirements.txt
└── README.md
```

---

## Env Vars

```bash
# .env — NEVER commit this file

# LLM
LLM_PROVIDER=openai              # openai | anthropic | groq
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...

# Cal.com booking
CALCOM_API_KEY=...
CALCOM_EVENT_TYPE_ID=...         # from Cal.com dashboard

# Voice (Phase 3)
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
DEEPGRAM_API_KEY=...
ELEVENLABS_API_KEY=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# Corpus paths (defaults shown)
RESUME_PATH=corpus/resume.pdf
ABOUT_ME_PATH=corpus/about_me.md
FAISS_INDEX_PATH=corpus/faiss_index
```

## Setup & Run

```bash
# 1. Create virtualenv
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Unix

# 2. Install deps
pip install -r requirements.txt

# 3. Copy env template and fill in keys
cp .env.example .env

# 4. Ingest corpus (builds FAISS index — run once, or after corpus changes)
python scripts/ingest_github.py   # clones repos, extracts READMEs + git logs
python -c "from persona.ingest import build_index; build_index()"

# 5. Run chat API
uvicorn api.main:app --reload --port 8000

# 6. Test
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "Why are you the right person for this role?", "history": []}'
```

---

## BUILD PHASES

### Phase 1 — Shared Brain (current)
- [x] Project scaffold + dirs + git init
- [x] Assignment PDF → docs/, resume → corpus/
- [x] about_me.md → corpus/
- [x] .gitignore + requirements.txt + .env.example
- [x] CLAUDE.md (this file)
- [ ] `scripts/ingest_github.py` — clone two flagship repos, extract README + git log
- [ ] `persona/ingest.py` — load all corpus docs → chunk → FAISS index
- [ ] `persona/retriever.py` — FAISS retriever returning chunks + source metadata
- [ ] `persona/prompts.py` — system prompt + guardrails
- [ ] `persona/llm.py` — provider-agnostic LLM wrapper
- [ ] `persona/brain.py` — Brain class tying it all together
- [ ] `persona/tools/booking.py` — Cal.com stub (clean interface)
- [ ] `api/main.py` — FastAPI POST /ask + GET /health
- [ ] `data/golden_qa.jsonl` — 5-10 grounded Q&A pairs
- [ ] Smoke-test: `python -c "from persona.brain import Brain; b=Brain(); print(b.answer('introduce yourself', []))"` passes
- [ ] git commit: "phase-1: shared brain + FastAPI /ask"

### Phase 2 — Calendar Integration
- [ ] Cal.com account setup + API key
- [ ] `persona/tools/booking.py` — real implementation (check_availability, book_slot)
- [ ] Wire booking tool into Brain's tool-use loop
- [ ] Test booking end-to-end from /ask
- [ ] git commit: "phase-2: cal.com booking tool"

### Phase 3 — Voice Agent
- [ ] Twilio US number purchase
- [ ] LiveKit Cloud project setup
- [ ] SIP trunk: Twilio → LiveKit
- [ ] `voice/agent.py` — LiveKit agent with Deepgram STT + ElevenLabs TTS + Brain
- [ ] Latency test: measure first-response time, target <2s
- [ ] Barge-in test: verify no crash
- [ ] git commit: "phase-3: livekit voice agent"

### Phase 4 — Chat UI
- [ ] React + Vite + Tailwind frontend
- [ ] Chat component, message history, source citations display
- [ ] Deploy to Vercel
- [ ] Test booking flow from chat UI
- [ ] git commit: "phase-4: chat frontend deployed"

### Phase 5 — Evals + Deliverables
- [ ] `evals/run_evals.py` — run golden_qa.jsonl, compute hallucination rate, retrieval precision/recall
- [ ] Voice eval: record N test calls, measure latency + booking success
- [ ] Write eval report (1-page PDF)
- [ ] Architecture diagram (draw.io or similar)
- [ ] Cost breakdown (per call / per chat session)
- [ ] Clean README with setup instructions
- [ ] Loom walkthrough (≤3 min)
- [ ] Submit: https://forms.gle/MrZMGCKikHaFkA3J9

---

## Conventions

**Teaching mode:** Before each step, explain what + why in plain English. After each step, 2-3 line "what changed + what to understand" recap.

**Model strategy:**
- DEFAULT: Sonnet 4.6 medium effort — 90% of this build
- ESCALATE: Opus 4.7 xhigh — hard voice-pipeline problems, barge-in bugs, deep architectural decisions. Drop back to Sonnet after.
- SKIP Opus 4.8 unless 4.7 genuinely fails
- HYBRID: use opusplan for voice agent planning phase (Opus architects, Sonnet executes)

**Grounding rules:** The persona ONLY answers from retrieved corpus. No invented facts. If retrieval returns nothing relevant, say "I don't have grounded information about that."

**Commit discipline:** After every meaningful step: update CLAUDE.md checkboxes, then `git commit` with clear message. Repo + CLAUDE.md = portable state for token runout or model switch.

**UI bar:** Clean, modern, minimal — NOT generic-AI-looking. No gradients-on-everything, no blinking cursors, no "ask me anything" placeholder. Think linear.app aesthetic.

**Security:** Never commit .env or secrets. Corpus files (resume.pdf, about_me.md) are gitignored — they're personal data and also not needed in the public repo.
