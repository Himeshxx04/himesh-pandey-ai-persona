"""
FastAPI chat backend.

POST /ask             { message, history }   →  { answer, sources, booking }
POST /ask/stream      { message, history }   →  SSE stream of tokens + sources/booking events
POST /voice/token     { caller_name? }        →  { token, room, url }    (browser → LiveKit)
POST /voice/callback  { phone_number }        →  initiates Twilio outbound to the caller; bridges to LiveKit
GET  /health                                   →  { status, provider, model }

Three channels into the same brain:
  • /ask           — HTTP chat
  • /voice/token   — WebRTC browser call (we mint JWT, dispatch agent)
  • /voice/callback — PSTN outbound (Twilio dials the user, bridges to LiveKit)
"""

import json
import os
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Deque, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# ── Lazy-init brain on startup ─────────────────────────────────────────────
_brain = None


def get_brain():
    global _brain
    if _brain is None:
        from persona import Brain
        _brain = Brain()
    return _brain


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up the brain (loads FAISS index + embeddings model) at startup
    # so the first /ask call isn't slow.
    print("[api] Warming up persona brain...")
    get_brain()
    print("[api] Brain ready.")
    yield


app = FastAPI(
    title="Himesh Pandey — AI Persona",
    description="RAG-grounded AI representative. POST /ask to chat.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production if needed
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Request / Response models ──────────────────────────────────────────────

class HistoryMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class AskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: List[HistoryMessage] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Why are you the right person for this AI Engineer role?",
                "history": [],
            }
        }


class BookingInfo(BaseModel):
    booking_id: str
    title: str
    start: str
    meet_url: Optional[str]
    confirmation_message: str


class AskResponse(BaseModel):
    answer: str
    sources: List[str]
    latency_ms: int
    booking: Optional[BookingInfo] = None


class VoiceTokenRequest(BaseModel):
    caller_name: Optional[str] = Field(
        None,
        max_length=80,
        description="Optional display name for the caller. Defaults to 'Web Caller'.",
    )


class VoiceTokenResponse(BaseModel):
    token: str = Field(..., description="LiveKit JWT — pass to LiveKit JS SDK")
    room: str = Field(..., description="Unique room name created for this call")
    url: str = Field(..., description="LiveKit WebSocket URL to connect to")
    agent: str = Field(..., description="Name of the dispatched agent")


class CallbackRequest(BaseModel):
    phone_number: str = Field(
        ...,
        min_length=8,
        max_length=20,
        description="E.164 phone number including '+'. Allowed countries: +91 (India), +1 (US/Canada).",
    )


class CallbackResponse(BaseModel):
    call_sid: str
    to: str
    message: str


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": os.getenv("LLM_PROVIDER", "openai"),
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    t0 = time.monotonic()

    brain = get_brain()
    history = [{"role": m.role, "content": m.content} for m in req.history]

    try:
        result = brain.answer(req.message, history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Brain error: {e}")

    latency_ms = int((time.monotonic() - t0) * 1000)

    booking_info = None
    if result.booking:
        b = result.booking
        booking_info = BookingInfo(
            booking_id=b.booking_id,
            title=b.title,
            start=b.start,
            meet_url=b.meet_url,
            confirmation_message=b.confirmation_message,
        )

    return AskResponse(
        answer=result.text,
        sources=result.sources,
        latency_ms=latency_ms,
        booking=booking_info,
    )


# ── Streaming chat ─────────────────────────────────────────────────────────

def _sse(event: str, payload: dict) -> str:
    """Encode one SSE event."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    """
    Server-Sent Events stream.

    Event sequence:
      event: sources   data: { sources: [...] }      (sent once, after retrieval)
      event: token     data: { text: "..." }         (sent many times, one per chunk)
      event: done      data: { booking?: {...} }     (sent once, end of stream)
      event: error     data: { message: "..." }      (only on failure)

    Booking intents route through brain.answer() (non-streaming) and arrive as
    a single 'done' event with the full text + booking object.
    """
    def event_gen():
        try:
            brain = get_brain()
            history = [{"role": m.role, "content": m.content} for m in req.history]

            # Booking intent → non-streaming, return full answer in 'done'
            if brain.is_booking_intent(req.message):
                result = brain.answer(req.message, history)
                yield _sse("sources", {"sources": result.sources})
                # send the full text in one token event so frontend can render it
                yield _sse("token", {"text": result.text})
                booking_payload = None
                if result.booking:
                    b = result.booking
                    booking_payload = {
                        "booking_id": b.booking_id,
                        "title": b.title,
                        "start": b.start,
                        "meet_url": b.meet_url,
                        "confirmation_message": b.confirmation_message,
                    }
                yield _sse("done", {"booking": booking_payload})
                return

            # Normal path: retrieve, then stream tokens from the LLM
            from persona.llm import stream as llm_stream

            sources, prompt_messages = brain.prepare(req.message, history)
            yield _sse("sources", {"sources": sources})

            for chunk in llm_stream(prompt_messages, temperature=0.3):
                if chunk:
                    yield _sse("token", {"text": chunk})

            yield _sse("done", {"booking": None})

        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering on Render
        },
    )


# ── Voice (browser-call) ───────────────────────────────────────────────────

@app.post("/voice/token", response_model=VoiceTokenResponse)
async def voice_token(req: VoiceTokenRequest):
    """
    Mint a LiveKit JWT for a browser participant and dispatch the
    `himesh-persona` agent into a fresh room.

    Browser then connects to LiveKit using @livekit/components-react and
    the agent (already in the room) starts speaking. Same agent + same Brain
    as the phone channel; only the transport differs.
    """
    livekit_url    = os.getenv("LIVEKIT_URL", "")
    api_key        = os.getenv("LIVEKIT_API_KEY", "")
    api_secret     = os.getenv("LIVEKIT_API_SECRET", "")

    if not (livekit_url and api_key and api_secret):
        raise HTTPException(
            status_code=500,
            detail="LiveKit env vars missing (LIVEKIT_URL / API_KEY / API_SECRET)",
        )

    # Local import keeps cold-start small for /health and /ask consumers.
    from livekit import api as lk_api

    # Fresh per-call room + identity. Short tokens so URLs/logs stay readable.
    room_name = f"web-call-{secrets.token_urlsafe(6)}"
    identity  = f"caller-{secrets.token_urlsafe(4)}"

    # 1) Mint the participant JWT
    token = (
        lk_api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(req.caller_name or "Web Caller")
        .with_grants(
            lk_api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .to_jwt()
    )

    # 2) Explicitly dispatch the himesh-persona worker into this room.
    # Without this, the worker only joins SIP-triggered rooms (via the dispatch
    # rule). For browser calls we tell LiveKit explicitly.
    lkapi = lk_api.LiveKitAPI(livekit_url, api_key, api_secret)
    try:
        await lkapi.agent_dispatch.create_dispatch(
            lk_api.CreateAgentDispatchRequest(
                agent_name="himesh-persona",
                room=room_name,
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to dispatch agent: {e}",
        )
    finally:
        await lkapi.aclose()

    return VoiceTokenResponse(
        token=token,
        room=room_name,
        url=livekit_url,
        agent="himesh-persona",
    )


# ── Voice (outbound callback) ──────────────────────────────────────────────

# Simple in-memory rate limiter: max N callback requests per IP in WINDOW seconds.
# Fine for a demo deployment with one process. For multi-replica prod, swap to Redis.
_CB_WINDOW_SECONDS = 3600   # 1 hour
_CB_MAX_PER_WINDOW = 50     # generous for dev. In production lower to ~5–10 to throttle abuse.
_cb_history: Dict[str, Deque[float]] = defaultdict(deque)

# Country prefixes we accept. Keeps Twilio costs bounded and blocks fraud
# routing (premium-rate numbers, exotic destinations).
_ALLOWED_PREFIXES = ("+91", "+1")

# Per-call max duration so an abandoned call can't bleed credit.
_CALL_TIME_LIMIT_S = 300  # 5 minutes


def _rate_limit_check(ip: str) -> None:
    """Raise HTTPException(429) if `ip` is over the callback quota."""
    now = time.time()
    history = _cb_history[ip]
    while history and history[0] < now - _CB_WINDOW_SECONDS:
        history.popleft()
    if len(history) >= _CB_MAX_PER_WINDOW:
        retry_after = int(_CB_WINDOW_SECONDS - (now - history[0]))
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit reached. Try again in {retry_after // 60 + 1} minute(s).",
        )


def _rate_limit_record(ip: str) -> None:
    """Record a successful call. Called only after Twilio accepts the dial."""
    _cb_history[ip].append(time.time())


@app.post("/voice/callback", response_model=CallbackResponse)
def voice_callback(req: CallbackRequest, request: Request):
    """
    Outbound callback: ask Twilio to dial `phone_number`. When the recipient
    answers, Twilio bridges the call into LiveKit via inline TwiML. LiveKit's
    inbound trunk + dispatch rule fires, himesh-persona joins the room, and
    the recipient hears the same agent as the inbound flow.

    This is the workaround for international callers — Indian recipients,
    for example, don't need ISD enabled to receive the call.
    """
    # 1. Rate-limit check (don't record yet — only count slots after Twilio accepts)
    client_ip = request.client.host if request.client else "unknown"
    _rate_limit_check(client_ip)

    # 2. Validate phone format + allowed country
    phone = req.phone_number.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+") or not phone[1:].isdigit():
        raise HTTPException(
            status_code=400,
            detail="Phone must be E.164 format, e.g. +919876543210",
        )
    if not phone.startswith(_ALLOWED_PREFIXES):
        raise HTTPException(
            status_code=400,
            detail=f"Only {', '.join(_ALLOWED_PREFIXES)} numbers are accepted.",
        )

    # 3. Required Twilio env
    sid    = os.getenv("TWILIO_ACCOUNT_SID", "")
    token  = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_  = os.getenv("TWILIO_PHONE_NUMBER", "")
    sip_uri = os.getenv("LIVEKIT_SIP_URI", "sip:fliuzwbmsck.sip.livekit.cloud")
    if not (sid and token and from_):
        raise HTTPException(
            status_code=500,
            detail="Twilio credentials not configured.",
        )
    # sip_uri in .env is stored as e.g. 'sip:fliuzwbmsck.sip.livekit.cloud'.
    # We need the host portion only — TwiML <Sip> takes a fully-qualified URI.
    sip_host = sip_uri[4:] if sip_uri.startswith("sip:") else sip_uri

    # 4. Inline TwiML: when the recipient answers, bridge to LiveKit's SIP URI.
    #
    # IMPORTANT: prefix the To-URI user part with the Twilio number so that
    # LiveKit's inbound trunk (which is filtered to accept calls TO +19378883660)
    # matches and accepts the bridged INVITE. Without the user prefix, the To:
    # header has no number → LiveKit's trunk filter rejects → call drops after
    # ~2 seconds.
    twilio_did = from_  # the same +1 number that's in the LiveKit trunk allowed-numbers list
    twiml = (
        f"<Response>"
        f"<Dial timeLimit=\"{_CALL_TIME_LIMIT_S}\" answerOnBridge=\"true\">"
        f"<Sip>sip:{twilio_did}@{sip_host}</Sip>"
        f"</Dial>"
        f"</Response>"
    )

    # 5. Fire the outbound call
    from twilio.rest import Client as TwilioClient
    from twilio.base.exceptions import TwilioRestException

    try:
        call = TwilioClient(sid, token).calls.create(
            to=phone,
            from_=from_,
            twiml=twiml,
        )
    except TwilioRestException as e:
        # Failure — do NOT consume a rate-limit slot. Surface Twilio's actual error.
        raise HTTPException(
            status_code=502,
            detail=f"Twilio error {e.code}: {e.msg}",
        )

    # Success — now record the rate-limit slot.
    _rate_limit_record(client_ip)

    return CallbackResponse(
        call_sid=call.sid,
        to=phone,
        message=f"Calling {phone} now. Your phone should ring within ~5 seconds.",
    )


# ── Voice (browser-call) ───────────────────────────────────────────────────
