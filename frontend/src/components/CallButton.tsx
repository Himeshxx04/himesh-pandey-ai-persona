import { useEffect, useRef, useState } from 'react'
import { Mic, MicOff, PhoneCall, PhoneOff, Loader2 } from 'lucide-react'
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useConnectionState,
  useLocalParticipant,
} from '@livekit/components-react'
import { ConnectionState } from 'livekit-client'
import '@livekit/components-styles'
import { getVoiceToken, type VoiceTokenResponse } from '../lib/api'

/**
 * Browser-based voice call to the himesh-persona agent.
 *
 * Idle state: gradient-bordered glass CTA with emerald inner glow.
 * In-call state: status row + mute + end-call controls inside a glass card.
 */
export function CallButton() {
  const [token, setToken] = useState<VoiceTokenResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function startCall() {
    setLoading(true)
    setError(null)
    try {
      const t = await getVoiceToken('Web Caller')
      setToken(t)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  function endCall() {
    setToken(null)
  }

  if (token) {
    return (
      <LiveKitRoom
        token={token.token}
        serverUrl={token.url}
        connect
        audio
        video={false}
        onDisconnected={endCall}
        className="contents"
      >
        <ActiveCallSurface onEnd={endCall} room={token.room} />
        <RoomAudioRenderer />
      </LiveKitRoom>
    )
  }

  // ── Idle CTA ───────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-3">
      <button
        type="button"
        onClick={startCall}
        disabled={loading}
        className="group relative overflow-hidden rounded-xl p-[1px] transition-all disabled:cursor-not-allowed disabled:opacity-60"
        style={{
          background:
            'linear-gradient(135deg, rgba(52,211,153,0.7) 0%, rgba(45,212,191,0.5) 50%, rgba(34,211,238,0.4) 100%)',
        }}
      >
        {/* Inner button face */}
        <span
          className="relative flex items-center justify-center gap-3 rounded-[11px] bg-canvas/85 px-6 py-5 text-[15px] font-medium text-ink backdrop-blur-sm transition-all group-hover:bg-canvas/75 group-hover:shadow-glow-emerald"
        >
          {loading ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin text-accent" />
              <span>Connecting…</span>
            </>
          ) : (
            <>
              <span className="relative flex h-9 w-9 items-center justify-center rounded-full bg-accent/15 ring-1 ring-accent/30">
                <PhoneCall className="h-4 w-4 text-accent" />
              </span>
              <span>
                Call this agent
                <span className="ml-1.5 text-ink-muted"> · in your browser</span>
              </span>
            </>
          )}
          {/* Soft inner highlight */}
          <span
            className="pointer-events-none absolute inset-x-12 top-0 h-px bg-gradient-to-r from-transparent via-white/15 to-transparent"
            aria-hidden
          />
        </span>
      </button>

      {error && (
        <p className="rounded-md border border-red-500/30 bg-red-500/5 px-3 py-2 text-sm text-red-400">
          Couldn't start the call: {error}
        </p>
      )}

      <p className="text-xs text-ink-dim">
        Browser-native voice over WebRTC · same agent as the phone line · allow microphone when prompted
      </p>
    </div>
  )
}

// ── In-call surface ──────────────────────────────────────────────────────

function ActiveCallSurface({
  onEnd,
  room,
}: {
  onEnd: () => void
  room: string
}) {
  const state = useConnectionState()
  const { localParticipant } = useLocalParticipant()
  const [muted, setMuted] = useState(false)
  const elapsedRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (state !== ConnectionState.Connected) return
    const start = Date.now()
    const id = window.setInterval(() => {
      if (!elapsedRef.current) return
      const s = Math.floor((Date.now() - start) / 1000)
      const m = Math.floor(s / 60)
      const r = s % 60
      elapsedRef.current.textContent = `${m}:${r.toString().padStart(2, '0')}`
    }, 1000)
    return () => window.clearInterval(id)
  }, [state])

  async function toggleMute() {
    const next = !muted
    setMuted(next)
    await localParticipant.setMicrophoneEnabled(!next)
  }

  const isConnected = state === ConnectionState.Connected
  const statusLabel = (() => {
    switch (state) {
      case ConnectionState.Connecting:    return 'Connecting'
      case ConnectionState.Reconnecting:  return 'Reconnecting'
      case ConnectionState.Connected:     return 'Connected'
      case ConnectionState.Disconnected:  return 'Disconnected'
      default:                            return 'Idle'
    }
  })()

  return (
    <div className="glass rounded-xl p-5 shadow-glow-soft">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2.5">
          <span className="relative inline-block h-2 w-2">
            <span
              className={
                'absolute inset-0 rounded-full ' +
                (isConnected ? 'bg-accent' : 'bg-ink-dim')
              }
            />
            {isConnected && (
              <span className="absolute inset-0 rounded-full bg-accent animate-pulse-dot" />
            )}
          </span>
          <span className="font-medium text-ink">{statusLabel}</span>
          <span className="text-ink-dim">·</span>
          <span ref={elapsedRef} className="font-mono text-xs text-ink-muted">
            0:00
          </span>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wider text-ink-dim">
          {room}
        </span>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <button
          type="button"
          onClick={toggleMute}
          className="glass glass-hover flex flex-1 items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm text-ink-muted hover:text-ink"
        >
          {muted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
          {muted ? 'Unmute' : 'Mute'}
        </button>
        <button
          type="button"
          onClick={onEnd}
          className="flex flex-1 items-center justify-center gap-2 rounded-md border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-medium text-red-400 transition-colors hover:border-red-500 hover:bg-red-500/20"
        >
          <PhoneOff className="h-4 w-4" />
          End call
        </button>
      </div>
    </div>
  )
}
