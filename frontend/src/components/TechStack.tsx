/**
 * Tech-stack panel. Grouped by domain, rendered as glass chips with a
 * subtle accent-tinted hover. No logos — keeps the look editorial.
 */

const GROUPS: { label: string; items: string[] }[] = [
  { label: 'Backend',  items: ['Python', 'FastAPI', 'PostgreSQL', 'SQLAlchemy', 'Docker'] },
  { label: 'ML',       items: ['PyTorch', 'scikit-learn'] },
  { label: 'Agentic',  items: ['LangGraph', 'LangChain', 'FastMCP', 'RAG', 'FAISS'] },
  { label: 'Voice',    items: ['LiveKit', 'Deepgram', 'ElevenLabs', 'Twilio SIP'] },
]

export function TechStack() {
  return (
    <div className="glass rounded-xl p-5">
      <div className="text-[10px] font-medium uppercase tracking-[0.22em] text-ink-dim">
        Stack
      </div>
      <div className="mt-4 flex flex-col gap-3.5">
        {GROUPS.map((g) => (
          <div key={g.label}>
            <div className="font-mono text-[10px] uppercase tracking-wider text-ink-dim">
              {g.label}
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {g.items.map((it) => (
                <span
                  key={it}
                  className="rounded-md border border-white/8 bg-white/[0.02] px-2 py-0.5 font-mono text-[11px] text-ink-muted transition-colors hover:border-accent/30 hover:text-ink"
                >
                  {it}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
