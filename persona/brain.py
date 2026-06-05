"""
Brain — the shared core persona.

Imported by BOTH:
  - api/main.py  (chat channel, HTTP)
  - voice/agent.py  (voice channel, in-process, no HTTP hop)

Usage:
    from persona import Brain
    brain = Brain()
    result = brain.answer("Why are you the right person?", history=[])
    print(result.text)
    print(result.sources)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

from dotenv import load_dotenv

from .ingest import build_index
from .retriever import Retriever, RetrievedChunk
from .prompts import build_prompt
from .llm import chat, stream, chat_with_tools
from .tools.booking import BookingTool, TimeSlot, BookingConfirmation, EmailParseError

load_dotenv()

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "corpus/faiss_index")


# ── OpenAI tool schemas for the chat channel ───────────────────────────────
# Voice uses LiveKit's @function_tool decorators; chat uses OpenAI's native
# function calling. Both ultimately call BookingTool — same brain.
_OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": (
                "Look up Himesh's open interview slots over the next 7 days. "
                "Call this when the user asks about availability or wants to "
                "schedule a call. Returns a list of open 30-minute slots."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date_hint": {
                        "type": "string",
                        "description": (
                            "Optional natural-language hint, e.g. 'this week', "
                            "'Tuesday'. Leave empty for next 7 days."
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_slot",
            "description": (
                "Book a specific interview slot on Himesh's Cal.com calendar. "
                "ONLY call this after the user has chosen a slot AND provided "
                "their name and email. Do not assume an email — the user must "
                "have given one."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_utc": {
                        "type": "string",
                        "description": (
                            "UTC start time copied verbatim from a previous "
                            "check_availability slot.utc_ref."
                        ),
                    },
                    "attendee_name": {
                        "type": "string",
                        "description": "The user's full name.",
                    },
                    "attendee_email": {
                        "type": "string",
                        "description": (
                            "The user's email address. Pass it exactly as the "
                            "user gave it — the booking layer auto-normalizes "
                            "spoken forms like 'at the rate' and 'dot'."
                        ),
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional one-line context about the meeting.",
                    },
                },
                "required": ["start_utc", "attendee_name", "attendee_email"],
            },
        },
    },
]


@dataclass
class AnswerResult:
    text: str
    sources: List[str] = field(default_factory=list)
    booking: Optional[BookingConfirmation] = None


class Brain:
    """
    The persona brain. Stateless per-call — pass history explicitly.

    Args:
        top_k: number of chunks to retrieve per query
        score_threshold: minimum cosine similarity to include a chunk
    """

    def __init__(self, top_k: int = 5, irrelevance_threshold: float = 0.10):
        store = build_index()
        self._retriever = Retriever(store, top_k=top_k, irrelevance_threshold=irrelevance_threshold)
        self._booking = BookingTool()

    # ── Booking intent detection ────────────────────────────────────────────

    _BOOKING_KEYWORDS = {
        "schedule", "book", "booking", "availability", "available", "calendar",
        "call", "meeting", "interview", "slot", "slots", "time", "when",
    }

    def _is_booking_intent(self, message: str) -> bool:
        words = set(message.lower().split())
        return bool(words & self._BOOKING_KEYWORDS)

    # Public alias — used by streaming endpoint to decide between
    # streaming a normal answer vs. running the full booking flow.
    def is_booking_intent(self, message: str) -> bool:
        return self._is_booking_intent(message)

    def prepare(self, message: str, history: List[dict]):
        """
        Retrieve corpus chunks + build the prompt without calling the LLM.
        Returns (sources, prompt_messages). Use this when you want to stream
        tokens yourself (e.g. SSE endpoint).
        """
        chunks = self._retriever.retrieve(message)
        context = self._retriever.format_context(chunks)
        sources = list({c.source for c in chunks})
        prompt_messages = build_prompt(context, history, message)
        return sources, prompt_messages

    # ── Main answer method ─────────────────────────────────────────────────

    def answer(
        self,
        message: str,
        history: List[dict],
        temperature: float = 0.3,
    ) -> AnswerResult:
        """
        Grounded answer using OpenAI function calling for booking tools.

        The LLM has access to two tools — check_availability and book_slot —
        and decides when to call them. No keyword regex; tool use is real.

        Args:
            message: current user turn
            history: list of {"role": "user"|"assistant", "content": str}
            temperature: passed to LLM

        Returns:
            AnswerResult with .text, .sources, and optionally .booking
        """
        # 1. Retrieve relevant context for RAG grounding
        chunks: List[RetrievedChunk] = self._retriever.retrieve(message)
        context = self._retriever.format_context(chunks)
        sources = list({c.source for c in chunks})

        # 2. Build the prompt
        messages = build_prompt(context, history, message)

        # 3. Make the booking tool result observable to the caller.
        # Tool handlers run inside chat_with_tools and may produce a
        # BookingConfirmation that the frontend should display.
        captured_booking: List[BookingConfirmation] = []

        def _handle_check_availability(args: dict) -> dict:
            slots = self._booking.check_availability(date_hint=args.get("date_hint", ""))
            return {
                "slots": [
                    {
                        "utc_ref": s.start_utc,
                        "human": s.formatted,
                    }
                    for s in slots[:6]
                ]
            }

        def _handle_book_slot(args: dict) -> dict:
            try:
                conf = self._booking.book_slot(
                    start_utc=args["start_utc"],
                    attendee_name=args["attendee_name"],
                    attendee_email=args["attendee_email"],
                    notes=args.get("notes", ""),
                )
            except EmailParseError as e:
                return {
                    "ok": False,
                    "error": "email_parse_failed",
                    "message": (
                        "I couldn't parse that email. Please ask the user to "
                        "type it again with @ and . — for example "
                        "'name@gmail.com'."
                    ),
                    "raw_email": args.get("attendee_email", ""),
                    "best_guess": str(e),
                }
            except Exception as e:
                return {
                    "ok": False,
                    "error": "booking_failed",
                    "message": str(e),
                }
            captured_booking.append(conf)
            return {
                "ok": True,
                "booking_id": conf.booking_id,
                "title": conf.title,
                "start": conf.start,
                "meet_url": conf.meet_url,
                "confirmation_message": conf.confirmation_message,
            }

        text, _called = chat_with_tools(
            messages=messages,
            tools=_OPENAI_TOOLS,
            tool_handlers={
                "check_availability": _handle_check_availability,
                "book_slot": _handle_book_slot,
            },
            temperature=temperature,
        )

        return AnswerResult(
            text=text,
            sources=sources,
            booking=captured_booking[0] if captured_booking else None,
        )

    def stream_answer(
        self,
        message: str,
        history: List[dict],
        temperature: float = 0.3,
    ) -> Iterator[str]:
        """
        Streaming variant for the voice agent (lowest latency first token).
        Yields text chunks. Does NOT handle booking tool — use answer() for that.
        """
        chunks = self._retriever.retrieve(message)
        context = self._retriever.format_context(chunks)
        messages = build_prompt(context, history, message)
        yield from stream(messages, temperature=temperature)

    # ── Booking handler ────────────────────────────────────────────────────

    def _handle_booking(
        self,
        message: str,
        history: List[dict],
        context: str,
        sources: List[str],
    ) -> Optional[AnswerResult]:
        """
        Simple booking flow: detect if user wants to see slots or confirm one.
        Returns an AnswerResult if we handled it, None to fall through to normal LLM.
        """
        msg_lower = message.lower()

        # Slot confirmation: "book the 10am slot" / "yes, the first one"
        confirm_words = {"book", "confirm", "yes", "go ahead", "that works", "let's do"}
        if any(w in msg_lower for w in confirm_words) and any(
            kw in msg_lower for kw in {"slot", "time", "am", "pm", "monday", "tuesday",
                                        "wednesday", "thursday", "friday"}
        ):
            # Let LLM handle asking for name/email before booking
            messages = build_prompt(
                context
                + "\n\n[SYSTEM NOTE: User wants to book. If you don't have their name and email yet, ask for them. If you do, call book_slot.]",
                history,
                message,
            )
            reply = chat(messages)
            return AnswerResult(text=reply, sources=sources)

        # Availability check
        if any(w in msg_lower for w in {"availability", "available", "when", "schedule", "slots"}):
            slots: List[TimeSlot] = self._booking.check_availability()
            if not slots:
                return AnswerResult(
                    text="My calendar looks pretty open — let me know what day works for you and I'll confirm a slot.",
                    sources=[],
                )
            slot_lines = "\n".join(
                f"- {s.formatted}  [utc_ref: {s.start_utc}]" for s in slots[:6]
            )
            messages = build_prompt(
                context + (
                    f"\n\n[AVAILABLE SLOTS FROM CALENDAR — next 7 days]\n{slot_lines}\n"
                    "[When the user picks a slot, ask for their name and email, then call complete_booking.]"
                ),
                history,
                message,
            )
            reply = chat(messages)
            return AnswerResult(text=reply, sources=sources)

        return None  # fall through to normal answer

    # ── Direct booking (for when LLM has extracted name + email + slot) ────

    def complete_booking(
        self,
        start_utc: str,
        attendee_name: str,
        attendee_email: str,
        notes: str = "",
    ) -> BookingConfirmation:
        """Called explicitly when name, email, and slot are all confirmed."""
        return self._booking.book_slot(start_utc, attendee_name, attendee_email, notes)
