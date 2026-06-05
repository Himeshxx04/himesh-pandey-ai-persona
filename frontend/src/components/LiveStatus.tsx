import { useEffect, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8001'

type HealthState = 'checking' | 'online' | 'offline'

export function LiveStatus() {
  const [state, setState] = useState<HealthState>('checking')

  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        const r = await fetch(`${API_BASE}/health`)
        if (!cancelled) setState(r.ok ? 'online' : 'offline')
      } catch {
        if (!cancelled) setState('offline')
      }
    }
    check()
    const id = window.setInterval(check, 30_000)
    return () => { cancelled = true; window.clearInterval(id) }
  }, [])

  return (
    <div className="glass inline-flex w-fit items-center gap-2.5 rounded-full px-3 py-1.5 text-[11px] uppercase tracking-[0.18em]">
      {state === 'online' ? (
        <>
          <span className="relative inline-block h-1.5 w-1.5">
            <span className="absolute inset-0 rounded-full bg-accent" />
            <span className="absolute inset-0 rounded-full bg-accent animate-pulse-dot" />
          </span>
          <span className="text-ink">Agent Online</span>
        </>
      ) : state === 'offline' ? (
        <>
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-red-500/70" />
          <span className="text-ink-muted">Agent Offline</span>
        </>
      ) : (
        <>
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-ink-dim animate-pulse-soft" />
          <span className="text-ink-dim">Checking…</span>
        </>
      )}
    </div>
  )
}
