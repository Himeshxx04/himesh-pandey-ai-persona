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
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

load_dotenv()


# ── Email normalization ────────────────────────────────────────────────────
# When the user speaks an email aloud, STT writes it as natural language:
#   "prasoon raj seven two six at the rate gmail dot com"
# We need to recover the actual address before sending to Cal.com. Without
# this, every voice booking fails with HTTP 400 from Cal.com's email validator.

_SPOKEN_NUMBERS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3",
    "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
    "nine": "9", "ten": "10", "double": "",   # "double oh" → "00" (handled below)
}

# Order matters — longer patterns first so "at the rate" matches before "at".
_SPOKEN_SYMBOLS: list[tuple[str, str]] = [
    (r"\bat\s+the\s+rate\s+of\b", "@"),
    (r"\bat\s+the\s+rate\b",      "@"),
    (r"\bat\s+sign\b",            "@"),
    (r"\bat\s+symbol\b",          "@"),
    (r"\bunder\s*score\b",        "_"),
    (r"\bdot\b",                  "."),
    (r"\bperiod\b",               "."),
    (r"\bpoint\b",                "."),
    (r"\bhyphen\b",               "-"),
    (r"\bdash\b",                 "-"),
    (r"\bminus\b",                "-"),
    (r"\bplus\b",                 "+"),
    # Plain "at" must come after symbol matches to avoid eating "@ at gmail"
    (r"\bat\b",                   "@"),
]

# A relaxed email pattern — good enough for the API; Cal.com does the strict check
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def normalize_email(raw: str) -> str:
    """
    Convert a spoken/typed email into the canonical form. Idempotent:
    already-clean inputs ('john@gmail.com') pass through unchanged.

        >>> normalize_email("prasoon raj seven two six at the rate gmail dot com")
        'prasoonraj726@gmail.com'
        >>> normalize_email("john.doe@example.com")
        'john.doe@example.com'
    """
    s = raw.strip().lower()

    # Replace spoken symbols (e.g. "at the rate" → "@", "dot" → ".")
    for pattern, replacement in _SPOKEN_SYMBOLS:
        s = re.sub(pattern, replacement, s)

    # Replace word-numbers with digits, word by word
    tokens = re.split(r"(\s+)", s)
    out_tokens = []
    for tok in tokens:
        out_tokens.append(_SPOKEN_NUMBERS.get(tok, tok))
    s = "".join(out_tokens)

    # Strip all remaining whitespace
    s = re.sub(r"\s+", "", s)

    return s


def is_valid_email(email: str) -> bool:
    """Loose validation — Cal.com does the authoritative check."""
    return bool(_EMAIL_RE.match(email))


class EmailParseError(ValueError):
    """Raised when an email can't be normalized to a valid address."""


class BookingUnavailableError(RuntimeError):
    """
    Raised when the Cal.com booking infrastructure itself is broken
    (event type deleted, API key invalid, endpoint moved). The LLM
    should surface this honestly to the user — NEVER fabricate slots
    or claim a booking happened. Recovery requires a human (Himesh)
    to fix Cal.com config.
    """

CALCOM_API_KEY       = os.getenv("CALCOM_API_KEY", "")
CALCOM_EVENT_TYPE_ID = int(os.getenv("CALCOM_EVENT_TYPE_ID", "5937335"))
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
        """
        Return available slots for the next 7 days (or 14 if fewer than 3 found).

        If `date_hint` matches a day in the result set (e.g. 'tomorrow',
        'Wednesday', 'Jun 10', 'next week'), narrow the returned slots to
        only that day/range. Falls back to the full distributed set if the
        hint doesn't parse.
        """
        if not CALCOM_API_KEY:
            return self._stub_slots()

        # Fetch a wider window so date hints can land on future days too.
        slots = self._fetch_slots(days=14)
        if not slots:
            slots = self._fetch_slots(days=21)

        if date_hint:
            filtered = self._filter_slots_by_hint(slots, date_hint)
            # Use filtered result only if non-empty; otherwise show everything
            # so caller doesn't think nothing is available.
            if filtered:
                return filtered

        return slots

    def _filter_slots_by_hint(self, slots: List[TimeSlot], hint: str) -> List[TimeSlot]:
        """
        Best-effort natural-language date filter. Examples that work:
          'tomorrow' / 'today'
          'monday', 'tue', 'wednesday' (any day name)
          'jun 10', 'june 10', '10th'
        Anything we can't parse → returns [] so caller falls back.
        """
        hint = hint.lower().strip()
        if not hint:
            return []

        now_ist = datetime.now(IST)

        # Build set of acceptable date strings in IST (YYYY-MM-DD)
        targets: set[str] = set()

        # "tomorrow"
        if "tomorrow" in hint:
            targets.add((now_ist + timedelta(days=1)).strftime("%Y-%m-%d"))
        # "today"
        if "today" in hint or "tonight" in hint:
            targets.add(now_ist.strftime("%Y-%m-%d"))
        # "this week" — next 5 weekdays
        if "this week" in hint or "next week" in hint:
            offset = 7 if "next week" in hint else 0
            for d in range(offset, offset + 7):
                targets.add((now_ist + timedelta(days=d)).strftime("%Y-%m-%d"))

        # Day names → find next matching weekday in the 14-day window
        day_names = {
            "monday": 0, "mon": 0,
            "tuesday": 1, "tue": 1, "tues": 1,
            "wednesday": 2, "wed": 2,
            "thursday": 3, "thu": 3, "thurs": 3,
            "friday": 4, "fri": 4,
            "saturday": 5, "sat": 5,
            "sunday": 6, "sun": 6,
        }
        for name, weekday_idx in day_names.items():
            if name in hint:
                for d in range(0, 14):
                    candidate = now_ist + timedelta(days=d)
                    if candidate.weekday() == weekday_idx:
                        targets.add(candidate.strftime("%Y-%m-%d"))
                        break

        # Month-day pattern: "jun 10", "june 10", "10 jun"
        months = {
            "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
            "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
            "jul": 7, "july": 7, "aug": 8, "august": 8,
            "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
            "nov": 11, "november": 11, "dec": 12, "december": 12,
        }
        day_num = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", hint)
        for mon_name, mon_idx in months.items():
            if mon_name in hint and day_num:
                day = int(day_num.group(1))
                year = now_ist.year
                # if month already passed this year, assume next year
                if mon_idx < now_ist.month:
                    year += 1
                targets.add(f"{year:04d}-{mon_idx:02d}-{day:02d}")

        if not targets:
            return []

        # Filter slots whose IST date matches any target
        return [
            s for s in slots
            if datetime.fromisoformat(s.start_utc.replace("Z", "+00:00"))
               .astimezone(IST).strftime("%Y-%m-%d") in targets
        ]

    def book_slot(
        self,
        start_utc: str,
        attendee_name: str,
        attendee_email: str,
        notes: str = "",
        attendee_timezone: str = "Asia/Kolkata",
    ) -> BookingConfirmation:
        """
        Book a confirmed slot.

        `attendee_email` may arrive as a spoken phrase from STT
        (e.g. "prasoon raj seven two six at the rate gmail dot com").
        We normalize before sending to Cal.com; raises EmailParseError
        if the result still doesn't look like an email.
        """
        # Guard: reject slots in the past — LLM sometimes hallucinates old dates
        # instead of using the utc_ref returned by check_availability.
        try:
            slot_dt = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
            if slot_dt < datetime.now(timezone.utc):
                raise ValueError(
                    f"Slot {start_utc} is in the past. "
                    "Please call check_availability first and use a utc_ref from that result."
                )
        except ValueError as e:
            if "in the past" in str(e):
                raise
            # Malformed ISO string — let Cal.com catch it with a clearer error below

        cleaned = normalize_email(attendee_email)
        if not is_valid_email(cleaned):
            raise EmailParseError(
                f"Could not parse '{attendee_email}' into a valid email. "
                f"Best guess after cleanup: '{cleaned}'."
            )

        if not CALCOM_API_KEY:
            return self._stub_booking(start_utc, attendee_name, cleaned)
        return self._real_booking(start_utc, attendee_name, cleaned, notes, attendee_timezone)

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
        # Distinguish "Cal.com is misconfigured" (404 event type, 401 bad key)
        # from transient errors. The former should NEVER trigger LLM
        # hallucination of fake slots — surface honestly to the user.
        if resp.status_code in (401, 403, 404):
            raise BookingUnavailableError(
                f"Cal.com /slots/available returned {resp.status_code}. "
                f"Likely cause: event type {CALCOM_EVENT_TYPE_ID} no longer exists "
                f"or API key invalid. Body: {resp.text[:200]}"
            )
        resp.raise_for_status()
        data = resp.json()

        # Group slots by date and DISTRIBUTE across days so the LLM sees
        # variety. Previously slots[:8] could return all 8 from a single
        # popular day, hiding availability on every other day in the window.
        slots_by_date: dict[str, List[TimeSlot]] = {}
        for date_str, day_slots in data.get("data", {}).get("slots", {}).items():
            for s in day_slots:
                slot = self._parse_slot(s["time"])
                slots_by_date.setdefault(date_str, []).append(slot)

        # Take the first 2 slots per available day, sorted chronologically.
        # Caps at ~12 total so the LLM can present them concisely.
        result: List[TimeSlot] = []
        for date_str in sorted(slots_by_date.keys()):
            day_slots = slots_by_date[date_str]
            result.extend(day_slots[:2])
            if len(result) >= 12:
                break
        return result

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
        if not resp.is_success:
            raise httpx.HTTPStatusError(
                f"{resp.status_code} from Cal.com — body: {resp.text[:400]}",
                request=resp.request,
                response=resp,
            )
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
