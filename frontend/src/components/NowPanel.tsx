/**
 * "What I'm building right now" — adds personality + signals momentum.
 * Static content; honest snapshot rather than mock-y telemetry.
 */
export function NowPanel() {
  return (
    <div className="glass relative overflow-hidden rounded-xl p-5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium uppercase tracking-[0.22em] text-ink-dim">
          Now Building
        </span>
        <span className="font-mono text-[10px] uppercase tracking-wider accent-text">
          Live
        </span>
      </div>

      <p className="mt-3 text-[14px] leading-[1.55] text-ink">
        A multi-channel <span className="accent-text font-medium">voice + chat AI representative</span>
        {' '}you're talking to. One shared brain, three interfaces — phone (Twilio SIP), browser
        (LiveKit WebRTC), and chat (FastAPI SSE).
      </p>

      <div className="mt-4 flex flex-wrap gap-1.5">
        {['LiveKit Agents', 'Deepgram Nova-3', 'ElevenLabs Flash v2.5', 'OpenAI gpt-4o-mini', 'FAISS', 'Cal.com'].map((tag) => (
          <span
            key={tag}
            className="rounded-md border border-white/10 bg-white/[0.02] px-2 py-0.5 font-mono text-[11px] text-ink-muted"
          >
            {tag}
          </span>
        ))}
      </div>

      {/* Decorative gradient ribbon */}
      <div
        className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full opacity-30 blur-2xl"
        style={{ background: 'radial-gradient(circle, #34d399 0%, transparent 70%)' }}
        aria-hidden
      />
    </div>
  )
}
