"""
Cal.com booking tool.

Interface is stable — the Brain calls these methods and doesn't care
whether it's a stub or a real API call. Phase 2 replaces the stub bodies
with real Cal.com v2 REST calls.

Cal.com v2 API docs: https://cal.com/docs/api-reference/v2/introduction
"""

import os
from dataclasses import dataclass
from typing import List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

CALCOM_API_KEY = os.getenv("CALCOM_API_KEY", "")
CALCOM_EVENT_TYPE_ID = os.getenv("CALCOM_EVENT_TYPE_ID", "")
CALCOM_USERNAME = os.getenv("CALCOM_USERNAME", "himesh-pandey")
CALCOM_BASE = "https://api.cal.com/v2"


@dataclass
class TimeSlot:
    start: str   # ISO-8601, e.g. "2026-06-10T10:00:00+05:30"
    end: str
    formatted: str  # human-readable, e.g. "Tue Jun 10, 10:00–10:30 AM IST"


@dataclass
class BookingConfirmation:
    booking_id: str
    title: str
    start: str
    end: str
    meet_url: Optional[str]
    confirmation_message: str


class BookingTool:
    """
    Tool for checking Himesh's calendar availability and booking interview slots.
    Imported by Brain and exposed as a callable tool to the LLM.
    """

    # ── Tool schema (used by LLM tool-use / function-calling) ──────────────
    TOOL_DEFINITIONS = [
        {
            "name": "check_availability",
            "description": (
                "Check Himesh's calendar for available interview slots. "
                "Call this when the user asks about availability or wants to book a call."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date_hint": {
                        "type": "string",
                        "description": (
                            "A natural-language date hint from the conversation, "
                            "e.g. 'this week', 'Monday', 'June 10'. "
                            "Leave empty to return slots for the next 7 days."
                        ),
                    }
                },
                "required": [],
            },
        },
        {
            "name": "book_slot",
            "description": (
                "Book a specific interview slot on Himesh's calendar. "
                "Call this once the user has confirmed a slot from check_availability."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {
                        "type": "string",
                        "description": "ISO-8601 start time, e.g. '2026-06-10T10:00:00+05:30'",
                    },
                    "attendee_name": {"type": "string"},
                    "attendee_email": {"type": "string"},
                    "notes": {
                        "type": "string",
                        "description": "Optional context about the meeting purpose.",
                    },
                },
                "required": ["start", "attendee_name", "attendee_email"],
            },
        },
    ]

    # ── Public methods ──────────────────────────────────────────────────────

    def check_availability(self, date_hint: str = "") -> List[TimeSlot]:
        """
        Return available slots.
        STUB: returns fake slots until Phase 2 wires up the real Cal.com API.
        """
        if not CALCOM_API_KEY:
            return self._stub_slots()
        return self._real_availability(date_hint)

    def book_slot(
        self,
        start: str,
        attendee_name: str,
        attendee_email: str,
        notes: str = "",
    ) -> BookingConfirmation:
        """
        Book a slot.
        STUB: returns a fake confirmation until Phase 2 wires up the real Cal.com API.
        """
        if not CALCOM_API_KEY:
            return self._stub_booking(start, attendee_name, attendee_email)
        return self._real_booking(start, attendee_name, attendee_email, notes)

    # ── Stub implementations (Phase 1) ─────────────────────────────────────

    def _stub_slots(self) -> List[TimeSlot]:
        """Placeholder slots — replaced by real Cal.com call in Phase 2."""
        return [
            TimeSlot(
                start="2026-06-10T10:00:00+05:30",
                end="2026-06-10T10:30:00+05:30",
                formatted="Tue Jun 10, 10:00–10:30 AM IST",
            ),
            TimeSlot(
                start="2026-06-10T15:00:00+05:30",
                end="2026-06-10T15:30:00+05:30",
                formatted="Tue Jun 10, 3:00–3:30 PM IST",
            ),
            TimeSlot(
                start="2026-06-11T11:00:00+05:30",
                end="2026-06-11T11:30:00+05:30",
                formatted="Wed Jun 11, 11:00–11:30 AM IST",
            ),
        ]

    def _stub_booking(self, start: str, name: str, email: str) -> BookingConfirmation:
        return BookingConfirmation(
            booking_id="stub-booking-001",
            title=f"Interview with {name}",
            start=start,
            end="",
            meet_url="https://cal.com/himesh-pandey/interview",
            confirmation_message=(
                f"Done! I've booked a 30-minute slot for {name} ({email}) "
                f"starting at {start}. You should receive a calendar invite shortly. "
                "Looking forward to the conversation!"
            ),
        )

    # ── Real Cal.com implementations (Phase 2) ─────────────────────────────

    def _real_availability(self, date_hint: str) -> List[TimeSlot]:
        """Cal.com v2 /slots endpoint."""
        # TODO Phase 2: implement
        # GET /slots/available?eventTypeId=...&startTime=...&endTime=...
        raise NotImplementedError("Phase 2: wire up Cal.com /slots endpoint")

    def _real_booking(
        self, start: str, name: str, email: str, notes: str
    ) -> BookingConfirmation:
        """Cal.com v2 /bookings endpoint."""
        # TODO Phase 2: implement
        # POST /bookings  body: { eventTypeId, start, attendee: { name, email, timeZone } }
        raise NotImplementedError("Phase 2: wire up Cal.com /bookings endpoint")
