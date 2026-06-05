/**
 * Backend client. Wraps POST /ask (chat) and POST /voice/token (browser call).
 *
 * Set VITE_API_BASE_URL in .env to point at the deployed FastAPI (Render).
 * Defaults to localhost for dev.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001'

// ── /ask ─────────────────────────────────────────────────────────────────

export interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface BookingInfo {
  booking_id: string
  title: string
  start: string
  meet_url?: string
  confirmation_message: string
}

export interface AskResponse {
  answer: string
  sources: string[]
  latency_ms: number
  booking?: BookingInfo
}

export async function ask(
  message: string,
  history: HistoryMessage[],
): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`ask failed: ${res.status} ${detail}`)
  }
  return res.json()
}

// ── Streaming variant ────────────────────────────────────────────────────

export interface AskStreamCallbacks {
  onSources?: (sources: string[]) => void
  onToken?: (text: string) => void
  onDone?: (info: { booking?: BookingInfo | null }) => void
  onError?: (message: string) => void
  signal?: AbortSignal
}

/**
 * POST /ask/stream — Server-Sent Events.
 * Calls callbacks as events arrive. Resolves when the stream ends.
 *
 * The backend emits four event types:
 *   sources  → { sources: string[] }   (once, before any token)
 *   token    → { text: string }        (many times, one per LLM chunk)
 *   done     → { booking: ... | null } (once, end of stream)
 *   error    → { message: string }     (only on failure)
 */
export async function askStream(
  message: string,
  history: HistoryMessage[],
  cb: AskStreamCallbacks,
): Promise<void> {
  const res = await fetch(`${API_BASE}/ask/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
    signal: cb.signal,
  })
  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => '')
    throw new Error(`stream failed: ${res.status} ${detail}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE events are separated by a blank line ("\n\n")
    let sepIdx
    while ((sepIdx = buffer.indexOf('\n\n')) >= 0) {
      const rawEvent = buffer.slice(0, sepIdx)
      buffer = buffer.slice(sepIdx + 2)
      parseEvent(rawEvent, cb)
    }
  }
}

function parseEvent(raw: string, cb: AskStreamCallbacks): void {
  let event = 'message'
  let data = ''
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      data += line.slice(5).trim()
    }
  }
  if (!data) return
  try {
    const parsed = JSON.parse(data)
    switch (event) {
      case 'sources': cb.onSources?.(parsed.sources ?? []); break
      case 'token':   cb.onToken?.(parsed.text ?? ''); break
      case 'done':    cb.onDone?.({ booking: parsed.booking ?? null }); break
      case 'error':   cb.onError?.(parsed.message ?? 'unknown error'); break
    }
  } catch {
    // ignore malformed JSON
  }
}

// ── /voice/token ─────────────────────────────────────────────────────────

export interface VoiceTokenResponse {
  token: string
  room: string
  url: string
  agent: string
}

export async function getVoiceToken(
  callerName?: string,
): Promise<VoiceTokenResponse> {
  const res = await fetch(`${API_BASE}/voice/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ caller_name: callerName ?? null }),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`voice token failed: ${res.status} ${detail}`)
  }
  return res.json()
}

// ── /voice/callback ──────────────────────────────────────────────────────

export interface CallbackResponse {
  call_sid: string
  to: string
  message: string
}

export async function requestCallback(phoneNumber: string): Promise<CallbackResponse> {
  const res = await fetch(`${API_BASE}/voice/callback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone_number: phoneNumber }),
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    // FastAPI surfaces validation/Twilio errors in `detail`
    const detail =
      typeof body?.detail === 'string'
        ? body.detail
        : `callback failed: ${res.status}`
    throw new Error(detail)
  }
  return body as CallbackResponse
}
