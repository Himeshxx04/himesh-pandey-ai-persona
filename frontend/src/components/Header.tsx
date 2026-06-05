import { ExternalLink, MapPin } from 'lucide-react'
import { LiveStatus } from './LiveStatus'

/**
 * Identity column. Editorial typography with a gradient-text headline and
 * a portrait card (initials) for visual anchoring. No avatar circles —
 * a flat letterform tile reads more designed than "generic AI avatar".
 */
export function Header() {
  return (
    <header className="flex flex-col gap-6 animate-rise">
      <LiveStatus />

      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2.5 text-[11px] uppercase tracking-[0.22em] text-ink-muted">
          <span className="accent-text font-semibold">AI Representative</span>
          <span className="h-1 w-1 rounded-full bg-ink-dim" aria-hidden />
          <span className="flex items-center gap-1.5">
            <MapPin className="h-3 w-3" />
            Bengaluru
          </span>
        </div>

        <h1 className="font-display text-[3.75rem] font-normal leading-[1.02] tracking-[-0.02em] sm:text-[4.5rem]">
          <span className="name-gradient">Himesh</span>
          <br />
          <span className="name-gradient italic">Pandey.</span>
        </h1>

        <p className="max-w-prose text-[15px] leading-[1.65] text-ink-muted">
          B.Tech (ECE) grad from PES University, building production-grade
          agentic systems with Python, FastAPI, LangGraph and RAG. This page
          is my AI representative — ask it anything about my background,
          projects, or availability. It books real calls on my calendar.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-ink-muted">
        <a
          href="https://github.com/Himeshxx04"
          target="_blank"
          rel="noreferrer"
          className="group inline-flex items-center gap-1.5 transition-colors hover:text-ink"
        >
          <span className="font-mono text-[13px]">github.com/Himeshxx04</span>
          <ExternalLink className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
        </a>
        <span className="text-ink-dim">·</span>
        <a
          href="mailto:pandeyhimesh09@gmail.com"
          className="font-mono text-[13px] transition-colors hover:text-ink"
        >
          pandeyhimesh09@gmail.com
        </a>
      </div>
    </header>
  )
}
