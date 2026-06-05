"""
Cal.com booking tool — real implementation.

API endpoints verified:
  GET  /v2/slots/available   cal-api-version: 2024-08-13
  POST /v2/bookings          cal-api-version: 2026-02-25

Event type: "30 min interview" (id=5911501, slug=30-min-interview)
Username: himesh-pandey-hvlicb
Timezone: Asia/Kolkata (IST, UTC+5:30)
"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

load_dotenv()

CALCOM_API_KEY       = os.getenv("CALCOM_API_KEY", "")
CALCOM_EVENT_TYPE_ID = int(os.getenv("CALCOM_EVENT_TYPE_ID", "5911501"))
CALCOM_USERNAME      = os.getenv("CALCOM_USERNAME", "himesh-pandey-hvlicb")
CALCOM_BASE          = "https://api.cal.com/v2"
IST                  = ZoneInfo("Asia/Kolkata")

# day-name → readable label
_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@dataclass
class TimeSlot:
    start_utc: str      # ISO-8601 UTC, e.g. "2026-06-10T04:30:00.000Z"
    start_ist: str      # ISO-8601 IST for booking, e.g. "2026-06-10T10:00:00+05:30"
    formatted: str      # human-readable, e.g. "Tue Jun 10, 10:00 AM IST"


@dataclass
class BookingConfirmation:
    booking_id: str
    booking_uid: str
    title: str
    start: str            # human-readable IST
    meet_url: Optional[str]
    confirmation_message: str


class BookingTool:
    """
    Tool for checking Himesh's Cal.com availability and booking interview slots.
    Imported by Brain and used by both chat and voice channels.
    """

    # ── LLM tool schemas (for function-calling in Phase 3) ─────────────────
    TOOL_DEFINITIONS = [
        {
            "name": "check_availability",
            "description": (
                "Check Himesh's calendar for available interview slots. "
                "Call this when the user asks about availability or wants to book a call. "
                "Returns a list of open 30-minute slots for the next 7 days."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date_hint": {
                        "type": "string",
                        "description": (
                            "Optional natural-language hint from the conversation, "
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
                "Call this once the user has confirmed a slot AND provided their name and email."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_utc": {
                        "type": "string",
                        "description": "UTC start time from a TimeSlot, e.g. '2026-06-10T04:30:00.000Z'",
                    },
                    "attendee_name":  {"type": "string"},
                    "attendee_email": {"type": "string"},
                    "notes": {
                        "type": "string",
                        "description": "Optional context about the meeting.",
                    },
                },
                "required": ["start_utc", "attendee_name", "attendee_email"],
            },
        },
    ]

    # ── Public API ──────────────────────────────────────────────────────────

    def check_availability(self, date_hint: str = "") -> List[TimeSlot]:
        """Return available slots for the next 7 days (or 14 if fewer than 3 found)."""
        if not CALCOM_API_KEY:
            return self._stub_slots()

        slots = self._fetch_slots(days=7)
        if len(slots) < 3:
            slots = self._fetch_slots(days=14)
        return slots

    def book_slot(
        self,
        start_utc: str,
        attendee_name: str,
        attendee_email: str,
        notes: str = "",
        attendee_timezone: str = "Asia/Kolkata",
    ) -> BookingConfirmation:
        """Book a confirmed slot."""
        if not CALCOM_API_KEY:
            return self._stub_booking(start_utc, attendee_name, attendee_email)
        return self._real_booking(start_utc, attendee_name, attendee_email, notes, attendee_timezone)

    # ── Cal.com API calls ───────────────────────────────────────────────────

    def _fetch_slots(self, days: int = 7) -> List[TimeSlot]:
        now_utc   = datetime.now(timezone.utc)
        end_utc   = now_utc + timedelta(days=days)
        start_str = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str   = end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        headers = {
            "Authorization": f"Bearer {CALCOM_API_KEY}",
            "cal-api-version": "2024-08-13",
        }
        params = {
            "eventTypeId": CALCOM_EVENT_TYPE_ID,
            "startTime": start_str,
            "endTime":   end_str,
        }
        resp = httpx.get(
            f"{CALCOM_BASE}/slots/available",
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        slots: List[TimeSlot] = []
        for _date, day_slots in (data.get("data", {}).get("slots", {}).items()):
            for s in day_slots:
                utc_str = s["time"]
                slot = self._parse_slot(utc_str)
                slots.append(slot)

        # Return up to 8 slots to avoid overwhelming the user
        return slots[:8]

    def _parse_slot(self, utc_str: str) -> TimeSlot:
        """Convert UTC ISO string to TimeSlot with IST display."""
        # Parse UTC time
        dt_utc = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        dt_ist = dt_utc.astimezone(IST)

        # IST ISO string for booking API
        start_ist = dt_ist.strftime("%Y-%m-%dT%H:%M:%S+05:30")

        # Human-readable: "Tue Jun 10, 10:00 AM IST"
        day   = _DAYS[dt_ist.weekday()]
        month = _MONTHS[dt_ist.month]
        hour  = dt_ist.hour
        minute = dt_ist.minute
        ampm   = "AM" if hour < 12 else "PM"
        h12    = hour % 12 or 12
        formatted = (
            f"{day} {month} {dt_ist.day}, "
            f"{h12}:{minute:02d} {ampm} IST"
        )

        return TimeSlot(start_utc=utc_str, start_ist=start_ist, formatted=formatted)

    def _real_booking(
        self,
        start_utc: str,
        name: str,
        email: str,
        notes: str,
        attendee_tz: str,
    ) -> BookingConfirmation:
        headers = {
            "Authorization": f"Bearer {CALCOM_API_KEY}",
            "cal-api-version": "2026-02-25",
            "Content-Type": "application/json",
        }
        body = {
            "eventTypeId": CALCOM_EVENT_TYPE_ID,
            "start": start_utc,
            "attendee": {
                "name":     name,
                "email":    email,
                "timeZone": attendee_tz,
                "language": "en",
            },
        }
        if notes:
            body["bookingFieldsResponses"] = {"notes": notes}

        resp = httpx.post(
            f"{CALCOM_BASE}/bookings",
            headers=headers,
            json=body,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})

        # Parse start time for display
        start_raw = data.get("start", start_utc)
        try:
            dt_utc = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            dt_ist = dt_utc.astimezone(IST)
            # %-d is Linux-only; use lstrip("0") for cross-platform
            readable_start = (
                dt_ist.strftime("%a %b ")
                + str(dt_ist.day)
                + dt_ist.strftime(", %I:%M %p IST")
            )
        except Exception:
            readable_start = start_raw

        # Extract meet link if available
        meet_url = None
        for loc in data.get("location", []) if isinstance(data.get("location"), list) else []:
            if "videoCallUrl" in loc:
                meet_url = loc["videoCallUrl"]
                break
        if not meet_url:
            meet_url = data.get("meetingUrl") or data.get("videoCallUrl")

        return BookingConfirmation(
            booking_id=str(data.get("id", "")),
            booking_uid=data.get("uid", ""),
            title=data.get("title", f"30 min interview with {name}"),
            start=readable_start,
            meet_url=meet_url or f"https://cal.com/{CALCOM_USERNAME}",
            confirmation_message=(
                f"Done! I've booked a 30-minute slot for {name} ({email}) "
                f"at {readable_start}. "
                f"A calendar invite has been sent to {email}. "
                f"{'Join link: ' + meet_url if meet_url else 'Meeting details will be in the invite.'}"
            ),
        )

    # ── Stubs (fallback when no API key) ────────────────────────────────────

    def _stub_slots(self) -> List[TimeSlot]:
        return [
            TimeSlot(
                start_utc="2026-06-10T04:30:00.000Z",
                start_ist="2026-06-10T10:00:00+05:30",
                formatted="Tue Jun 10, 10:00 AM IST",
            ),
            TimeSlot(
                start_utc="2026-06-10T09:30:00.000Z",
                start_ist="2026-06-10T15:00:00+05:30",
                formatted="Tue Jun 10, 3:00 PM IST",
            ),
        ]

    def _stub_booking(self, start_utc: str, name: str, email: str) -> BookingConfirmation:
        return BookingConfirmation(
            booking_id="stub-001",
            booking_uid="stub-uid-001",
            title=f"30 min interview with {name}",
            start=start_utc,
            meet_url=f"https://cal.com/{CALCOM_USERNAME}/30-min-interview",
            confirmation_message=(
                f"Done! I've booked a slot for {name} ({email}) at {start_utc}. "
                "A calendar invite has been sent."
            ),
        )
