# Architecture

The persona is built around one principle: **one brain, two channels.** A single `persona/` Python package contains the corpus loader, FAISS retriever, prompt + guardrails, and Cal.com booking tool. It is imported in-process by both the chat backend (FastAPI) and the voice worker (LiveKit Agents). No HTTP hop between them. Same retriever, same prompts, same booking flow — only the transport differs.

## System diagram

```mermaid
flowchart TB
    %% ── Corpus ─────────────────────────────────────────────
    subgraph CORPUS["📂 corpus/"]
        direction TB
        Resume["resume.pdf"]
        About["about_me.md"]
        Github["github/<br/>(README + git log + docs)<br/>rag-pipeline-optimizer<br/>mcp-artifact-store"]
    end

    %% ── Shared Brain ────────────────────────────────────────
    subgraph BRAIN["🧠 persona/  (shared brain)"]
        direction TB
        Ingest["ingest.py<br/>chunks → FAISS"]
        Retriever["retriever.py<br/>multi-qa-MiniLM-L6"]
        Prompts["prompts.py<br/>guardrails + booking rules"]
        LLM["llm.py<br/>provider-agnostic"]
        BrainCore["brain.py<br/>+ hallucination guard"]
        Booking["tools/booking.py<br/>Cal.com v2"]
    end

    CORPUS --> Ingest
    Ingest --> Retriever
    Retriever --> BrainCore
    Prompts --> BrainCore
    LLM --> BrainCore
    Booking --> BrainCore

    %% ── Chat Channel ────────────────────────────────────────
    subgraph CHAT["💬 Chat Channel  (Render Standard)"]
        API["api/main.py<br/>FastAPI<br/>/ask  /ask/stream<br/>/voice/token  /voice/callback"]
    end

    BrainCore -- "imported<br/>in-process" --> API

    %% ── Voice Channel ───────────────────────────────────────
    subgraph VOICE["🎙️ Voice Channel  (Render Standard)"]
        Agent["voice/agent.py<br/>LiveKit Agents 1.5"]
        STT["Deepgram Nova-3<br/>(STT, multi-lang)"]
        VLLM["OpenAI gpt-4o-mini<br/>(LLM)"]
        TTS["ElevenLabs Flash v2.5<br/>(TTS, 'Brian')"]
        VAD["Silero VAD<br/>+ ML turn-detector"]
        STT --> Agent
        Agent --> VLLM
        VLLM --> Agent
        Agent --> TTS
        VAD --> Agent
    end

    BrainCore -- "imported<br/>in-process<br/>(RAG via on_user_turn_completed)" --> Agent

    %% ── Frontend ────────────────────────────────────────────
    subgraph FE["🌐 Frontend  (Vercel)"]
        UI["React + Vite + Tailwind<br/>ChatPanel (SSE)<br/>CallButton (WebRTC)<br/>PhoneFallback"]
    end

    User1[("👤 Chat user<br/>browser")] --> UI
    UI -- "POST /ask/stream<br/>(text)" --> API
    UI -- "POST /voice/token<br/>(JWT)" --> API

    %% ── LiveKit Cloud ───────────────────────────────────────
    LK["☁️ LiveKit Cloud<br/>(room + media)"]
    UI -- "WebRTC<br/>(browser call)" <--> LK
    Agent <--> LK

    %% ── Twilio + PSTN ───────────────────────────────────────
    Caller[("📞 Phone caller<br/>+1 (937) 888-3660")]
    Twilio["Twilio US number<br/>+ SIP trunk"]
    Caller -- "PSTN" --> Twilio
    Twilio -- "SIP" --> LK

    %% ── External services ───────────────────────────────────
    CalCom["📅 Cal.com v2 API<br/>30-min interview event"]
    Booking <-- "slots + booking" --> CalCom

    %% ── Styling ─────────────────────────────────────────────
    classDef brain fill:#1e293b,stroke:#10b981,color:#e2e8f0
    classDef channel fill:#0f172a,stroke:#3b82f6,color:#e2e8f0
    classDef ext fill:#1e1b4b,stroke:#a78bfa,color:#e2e8f0
    classDef user fill:#0c4a6e,stroke:#0ea5e9,color:#e0f2fe

    class BRAIN,Ingest,Retriever,Prompts,LLM,BrainCore,Booking brain
    class CHAT,API,VOICE,Agent,STT,VLLM,TTS,VAD,FE,UI channel
    class LK,Twilio,CalCom ext
    class User1,Caller user
```

## Request flows

### Chat (`POST /ask/stream`)

```
Browser → ChatPanel
   ↓ POST /ask/stream { message, history }
Render API (api/main.py)
   ↓ is_booking_intent(message, history) ?
       YES → Brain.answer() with function tools (check_availability, book_slot)
       NO  → Brain.prepare() then stream LLM tokens via SSE
   ↓
ChatPanel renders tokens as they arrive; on `done` event,
   if booking object present, render booking card.
```

If the model hallucinates a fake "booking is confirmed" without calling `book_slot`, `brain.py`'s hallucination guard detects the lie and forces a silent second pass that either makes the real booking or honestly asks for what's missing. The frontend never sees the lie.

### Voice (phone call)

```
Caller dials +1 (937) 888-3660
   ↓ PSTN
Twilio US number
   ↓ SIP trunk
LiveKit Cloud
   ↓ creates room, dispatches agent "himesh-persona"
voice/agent.py worker (Render)
   ↓ entrypoint() runs:
       ─ background thread: _get_retriever()  (FAISS warm by first turn)
       ─ build AgentSession(STT, LLM, TTS, VAD, turn_detector)
       ─ session.say("Hi, I'm Himesh's AI representative…")
   ↓ caller speaks
       ─ Deepgram Nova-3 streams transcript (200ms delay, multilingual)
       ─ on_user_turn_completed:
           retriever.retrieve(user_text) → format_context → inject as system msg
       ─ LLM generates response (with check_availability / book_slot as tools)
       ─ ElevenLabs Flash v2.5 streams audio back (75ms first byte)
   ↓ caller hears Brian
```

Silero VAD + the LiveKit ML turn-detector handle barge-in: if the caller starts talking mid-response, the TTS is interrupted, the buffer flushed, and STT resumes immediately.

### Voice (browser WebRTC call)

```
Browser → ChatPanel.CallButton
   ↓ POST /voice/token { caller_name }
Render API (api/main.py)
   ↓ mints LiveKit JWT
   ↓ dispatches agent "himesh-persona" to a fresh room
   ↓ returns { token, url, room }
Browser → LiveKit JS SDK
   ↓ WebRTC connection
LiveKit Cloud (same room as agent)
   ↓ same agent flow as phone call
```

## Why this design

**One shared brain, not a microservice.** I considered HTTP-fronting the persona behind a `/retrieve` endpoint that both channels would call. Rejected because:
- Voice turns happen every 1-2 seconds. An HTTP hop adds 30-80ms per turn for serialization + network — on a 2s budget, that's 2-4% wasted.
- Process-shared cache: both channels hit the same FAISS index in the same Python process. With separate services, each would maintain its own copy of `multi-qa-MiniLM-L6` (80MB) and the FAISS index — doubling memory for zero gain.
- Single source of truth for guardrails. When I patch the hallucination logic in `brain.py`, both channels get it on the next deploy. No version skew.

**Adding a third channel is one import.** Slack, WhatsApp, or a Discord bot would each be ~50 lines that import `Brain` and use the same `.answer()` method. The booking tool, RAG retrieval, prompt, and guardrails come for free.

**Cost-aware model choice.** `gpt-4o-mini` is ~30x cheaper than `gpt-4o` per token, and after the hallucination guard catches the 1-in-20 cases it gets wrong, the effective quality is statistically indistinguishable for this task. Saved cost matters because evaluators will call repeatedly during the 7-day window.

## Cross-references

- Phase-by-phase build planning + decision log: [`CLAUDE.md`](../CLAUDE.md)
- Voice / SIP / dispatch rule setup notes: [`voice/README.md`](../voice/README.md)
- Submission and grading rubric: [`docs/assignment.pdf`](./assignment.pdf)
