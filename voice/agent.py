"""
LiveKit Agents voice worker — Himesh Pandey persona over the phone.

Architecture: "one brain, two channels"
  - imports persona.brain.Retriever + persona.prompts.SYSTEM_PROMPT + BookingTool
  - Deepgram Nova-3 STT  → OpenAI gpt-4o-mini LLM  → ElevenLabs Flash v2.5 TTS
  - Silero VAD + LiveKit's turn-detector plugin for barge-in / interruption

RAG hook:  on_user_turn_completed runs the retriever on every user turn and
           injects the top-k chunks into the chat context as a system message
           BEFORE the LLM generates. Same retrieval the chat /ask endpoint uses.

Booking:   @function_tool wraps BookingTool.check_availability and book_slot.
           The LLM decides when to call them based on the system prompt.

Run modes:
    python voice/agent.py dev       # local dev — connects to LiveKit Cloud, joins playground
    python voice/agent.py start     # production — same connection, no dev features
    python voice/agent.py download-files  # one-time: download silero + turn-detector models

Environment variables required (already in .env):
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
    DEEPGRAM_API_KEY
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID
    LLM_API_KEY (OpenAI)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Annotated

# Make the repo root importable so `from persona import ...` works
# when this file is launched directly from voice/.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    ChatContext,
    ChatMessage,
    JobContext,
    JobProcess,
    RunContext,
    WorkerOptions,
    function_tool,
)
from livekit.plugins import deepgram, elevenlabs, openai, silero

# Optional ML-based end-of-utterance detection. Imported lazily so the agent
# still runs if the plugin model isn't downloaded yet.
try:
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
    HAS_TURN_DETECTOR = True
except Exception:
    HAS_TURN_DETECTOR = False

# Lightweight persona imports only. The HEAVY retriever (sentence-transformers
# + sklearn + scipy + FAISS) is loaded lazily inside _get_retriever() so that:
#   (a) the inference subprocess (which never needs the retriever, only the
#       turn-detector + VAD models) doesn't pay the import cost, and
#   (b) the entrypoint job pool warms it once via prewarm_fnc, ahead of any
#       call, so the first user turn isn't slowed by retriever cold-start.
from persona.prompts import SYSTEM_PROMPT
from persona.tools.booking import BookingTool, EmailParseError

logger = logging.getLogger("voice-agent")
logging.basicConfig(level=logging.INFO)


# ── Voice-output suffix appended to the chat system prompt ─────────────────
# Substance is identical to chat (same persona, same guardrails). Only the
# delivery rules change because TTS reads markdown literally.
VOICE_OUTPUT_RULES = """

VOICE-OUTPUT RULES (this conversation is being SPOKEN over a phone):
- Keep answers to 1-3 sentences unless the caller asks for depth
- No markdown, no asterisks, no bullet points, no code blocks, no URLs
- Use natural spoken phrasing: "I built two projects" not "Two projects: 1. ..."
- When listing 2-3 things, use "first... second... and third..."
- Spell out numbers under ten; pronounce acronyms naturally
- If you're about to call a tool (checking availability / booking), say one short
  filler phrase first so the caller hears something while the API runs:
  e.g. "Let me check my calendar real quick."

BOOKING — EMAIL CONFIRMATION (CRITICAL):
When the caller gives you their email aloud, the speech-to-text system writes
it as natural language — "at" becomes "at the rate", "." becomes "dot",
digits become words, and spaces appear between every token. BEFORE you call
book_slot:
1. Read the email back to the caller in a natural form, e.g.
   "Just to confirm — that's prasoon raj seven two six at gmail dot com,
   spelled P-R-A-S-O-O-N-R-A-J-7-2-6 at gmail.com — correct?"
2. Wait for them to confirm yes / correct it.
3. Only then call book_slot, and pass the email EXACTLY as the caller spoke
   it (don't try to reformat it yourself — the booking system normalizes
   spoken forms automatically).
4. If the booking tool replies with "I had trouble understanding the email",
   ask the caller to spell it letter by letter.

This rule is non-negotiable. A wrong email means no calendar invite reaches
the caller — the entire point of the booking flow.
"""


# ── Lazy singletons ────────────────────────────────────────────────────────
# Heavy retriever is built on first access (inside the entrypoint process pool,
# via prewarm_fnc). The inference subprocess never calls these.
_retriever = None
_booking = BookingTool()    # lightweight — just an httpx wrapper


def _get_retriever():
    """Lazy-build the FAISS retriever. Called from prewarm_fnc and on_user_turn_completed."""
    global _retriever
    if _retriever is None:
        # Deferred imports — these pull sentence-transformers + sklearn + scipy + FAISS.
        from persona.ingest import build_index
        from persona.retriever import Retriever

        logger.info("loading FAISS retriever for voice agent...")
        store = build_index()
        _retriever = Retriever(store, top_k=5, irrelevance_threshold=0.10)
        logger.info("retriever ready (%d index).", store.index.ntotal if hasattr(store, "index") else -1)
    return _retriever


# ────────────────────────────────────────────────────────────────────────────
# Agent
# ────────────────────────────────────────────────────────────────────────────
class HimeshAgent(Agent):
    """
    Voice persona. Shares prompts + retriever + booking tool with the chat brain.
    """

    def __init__(self) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT + VOICE_OUTPUT_RULES,
        )

    # ── RAG hook: runs before the LLM responds to each user turn ───────────
    async def on_user_turn_completed(
        self,
        turn_ctx: ChatContext,
        new_message: ChatMessage,
    ) -> None:
        """
        After the user finishes speaking and STT produces a transcript,
        retrieve relevant corpus chunks and inject them as a system message
        in the chat context BEFORE the LLM generates its reply.
        """
        user_text = new_message.text_content
        if not user_text:
            return

        try:
            retriever = _get_retriever()
            chunks = retriever.retrieve(user_text)
            context = retriever.format_context(chunks)
            if context:
                turn_ctx.add_message(
                    role="system",
                    content=f"[RETRIEVED CONTEXT for the question just asked]\n{context}",
                )
                logger.info("RAG: injected %d chunks for: %r", len(chunks), user_text[:80])
            else:
                turn_ctx.add_message(
                    role="system",
                    content="[No relevant context found for this question. Be honest about not knowing.]",
                )
        except Exception as e:
            logger.exception("RAG retrieval failed: %s", e)
            # Don't crash the turn — let the LLM answer ungrounded with the system prompt
            # telling it to admit when it doesn't know.

    # ── Function tools: Cal.com booking ────────────────────────────────────
    @function_tool
    async def check_availability(
        self,
        context: RunContext,
        date_hint: Annotated[
            str,
            "Optional natural-language hint like 'this week' or 'Tuesday'. Leave blank for next 7 days."
        ] = "",
    ) -> str:
        """
        Look up Himesh's open interview slots over the next 7 days.
        Call this when the caller asks about availability or wants to schedule.
        Returns a spoken-friendly list of the next few available slots.
        """
        logger.info("tool: check_availability(date_hint=%r)", date_hint)
        try:
            slots = _booking.check_availability(date_hint=date_hint)
        except Exception as e:
            logger.exception("check_availability failed: %s", e)
            return (
                "I had trouble reaching my calendar just now. "
                "Could you tell me your preferred day and time and I'll confirm by email?"
            )

        if not slots:
            return (
                "My calendar's pretty open this week. "
                "Tell me what day and time works for you and I'll lock it in."
            )

        top = slots[:4]
        lines = []
        for s in top:
            # Keep the UTC reference embedded so the LLM has it when the caller picks one
            lines.append(f"{s.formatted}  [utc_ref={s.start_utc}]")

        return (
            "Here are the next openings I have:\n"
            + "\n".join(lines)
            + "\n\nCRITICAL: when you call book_slot, the start_utc argument MUST be copied "
              "CHARACTER-FOR-CHARACTER from one of the utc_ref values above. "
              "Do NOT construct or guess a date — use only the exact utc_ref strings shown."
        )

    @function_tool
    async def book_slot(
        self,
        context: RunContext,
        start_utc: Annotated[str, "UTC start time copied verbatim from a check_availability utc_ref"],
        attendee_name: Annotated[str, "The caller's full name"],
        attendee_email: Annotated[str, "The caller's email address"],
        notes: Annotated[str, "Optional one-line context about the meeting"] = "",
    ) -> str:
        """
        Book a confirmed slot on Himesh's Cal.com calendar.
        Only call AFTER the caller has chosen a slot AND given their name and email.
        The start_utc MUST be an exact utc_ref string from check_availability — never construct one yourself.
        Returns a confirmation message safe to read aloud.
        """
        logger.info(
            "tool: book_slot(start=%s, name=%s, email=%s)",
            start_utc, attendee_name, attendee_email,
        )
        try:
            confirmation = _booking.book_slot(
                start_utc=start_utc,
                attendee_name=attendee_name,
                attendee_email=attendee_email,
                notes=notes,
            )
        except EmailParseError as e:
            # STT mangled the email and our normalizer couldn't recover it.
            # Surface a CLEAR action for the LLM so it asks the user to spell.
            logger.warning("book_slot email parse failure: %s", e)
            return (
                "I had trouble understanding the email address. "
                "Could you spell it letter by letter? For example, "
                "'p as in peter, r, a, s, o, o, n, at gmail dot com'. "
                "Once I have it I'll lock in the slot."
            )
        except Exception as e:
            logger.exception("book_slot failed: %s", e)
            return (
                "Something went wrong on my calendar side. "
                "Could you send me an email and I'll confirm the slot manually?"
            )

        # confirmation.confirmation_message is already phrased for speech
        return confirmation.confirmation_message


# ────────────────────────────────────────────────────────────────────────────
# Entrypoint — runs per call / per playground session
# ────────────────────────────────────────────────────────────────────────────
async def entrypoint(ctx: JobContext) -> None:
    """
    Connect to the LiveKit room, set up the agent session, greet the caller.
    """
    logger.info("agent entrypoint: connecting to room %s", ctx.room.name)
    await ctx.connect()

    # Build the session. Models chosen for latency:
    #   STT: Deepgram Nova-3 streaming (~200ms)
    #   LLM: OpenAI gpt-4o-mini (~600-900ms TTFT)
    #   TTS: ElevenLabs Flash v2.5 (~75ms first byte)
    #   VAD: Silero (local, ~10ms)
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
    if not voice_id:
        raise RuntimeError("ELEVENLABS_VOICE_ID is not set in .env")

    session_kwargs = dict(
        stt=deepgram.STT(
            model="nova-3",
            language="multi",
        ),
        llm=openai.LLM(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("LLM_API_KEY"),
            temperature=0.3,
        ),
        tts=elevenlabs.TTS(
            voice_id=voice_id,
            model="eleven_flash_v2_5",
            api_key=os.getenv("ELEVENLABS_API_KEY"),
        ),
        vad=ctx.proc.userdata.get("vad") or silero.VAD.load(),
    )

    # Add ML turn-detector if the plugin model has been downloaded.
    # On first run, do: python voice/agent.py download-files
    if HAS_TURN_DETECTOR:
        try:
            session_kwargs["turn_detection"] = MultilingualModel()
        except Exception as e:
            logger.warning("turn_detector model not loaded (%s) — falling back to VAD turn-taking.", e)

    session = AgentSession(**session_kwargs)

    await session.start(
        agent=HimeshAgent(),
        room=ctx.room,
    )

    # Opening line — deterministic TTS so the greeting is identical on every
    # call. Avoids occasional LLM gibberish at call start when we ask the
    # model to "greet in one sentence" and it interprets that freely.
    await session.say(
        "Hi, I'm Himesh's AI representative — happy to help with questions "
        "about his projects, background, or scheduling a call. What would "
        "you like to know?",
        allow_interruptions=True,
    )


def prewarm(proc: JobProcess) -> None:
    """
    Runs ONCE per entrypoint process before any job is dispatched.
    Loads the FAISS retriever + Silero VAD into the process so the first
    call doesn't pay any cold-start cost. The inference subprocess does
    NOT run this function (it's a different process pool).
    """
    logger.info("prewarm: loading retriever + VAD...")
    proc.userdata["retriever"] = _get_retriever()
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("prewarm: done.")


if __name__ == "__main__":
    agents.cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name="himesh-persona",   # shows up in LiveKit Console dropdown + Twilio dispatch rule
            # Cold-start tuning.
            # Our prewarm loads sentence-transformers + FAISS + retriever and
            # takes ~12s on first run. Default initialize_process_timeout is
            # 10s, which caused the first job to timeout and retry — a 30s
            # latency hit on the first call.
            initialize_process_timeout=45.0,
            # Keep one process warm and ready at all times. Means the first
            # incoming call hits an already-loaded worker instead of paying
            # the 12s setup cost. The cost is one always-running Python
            # process — fine for our scale.
            num_idle_processes=1,
        )
    )
