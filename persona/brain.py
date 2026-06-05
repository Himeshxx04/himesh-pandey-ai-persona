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
from .llm import chat, stream
from .tools.booking import BookingTool, TimeSlot, BookingConfirmation

load_dotenv()

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "corpus/faiss_index")


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

    # ── Main answer method ─────────────────────────────────────────────────

    def answer(
        self,
        message: str,
        history: List[dict],
        temperature: float = 0.3,
    ) -> AnswerResult:
        """
        Grounded answer to a message, given conversation history.

        Args:
            message: current user turn
            history: list of {"role": "user"|"assistant", "content": str}
            temperature: passed to LLM (lower = more grounded)

        Returns:
            AnswerResult with .text, .sources, and optionally .booking
        """
        # 1. Retrieve relevant context
        chunks: List[RetrievedChunk] = self._retriever.retrieve(message)
        context = self._retriever.format_context(chunks)
        sources = list({c.source for c in chunks})

        # 2. Check for booking intent
        if self._is_booking_intent(message):
            booking_result = self._handle_booking(message, history, context, sources)
            if booking_result:
                return booking_result

        # 3. Build prompt and call LLM
        messages = build_prompt(context, history, message)
        reply = chat(messages, temperature=temperature)

        return AnswerResult(text=reply, sources=sources)

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
            slot_list = "\n".join(f"- {s.formatted}" for s in slots[:5])
            messages = build_prompt(
                context + f"\n\n[AVAILABLE SLOTS FROM CALENDAR]\n{slot_list}",
                history,
                message,
            )
            reply = chat(messages)
            return AnswerResult(text=reply, sources=sources)

        return None  # fall through to normal answer

    # ── Direct booking (for when LLM has extracted name + email + slot) ────

    def complete_booking(
        self,
        start: str,
        attendee_name: str,
        attendee_email: str,
        notes: str = "",
    ) -> BookingConfirmation:
        """Called explicitly when name, email, and slot are all confirmed."""
        return self._booking.book_slot(start, attendee_name, attendee_email, notes)
