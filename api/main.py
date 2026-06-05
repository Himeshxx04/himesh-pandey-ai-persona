"""
FastAPI chat backend.

POST /ask   { message, history }  →  { answer, sources, booking }
GET  /health  →  { status, provider, model }
"""

import os
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
