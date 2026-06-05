import { ArrowUpRight, Database, Network } from 'lucide-react'

interface Project {
  title: string
  blurb: string
  href: string
  stack: string[]
  icon: 'network' | 'database'
}

const PROJECTS: Project[] = [
  {
    title: 'MCP Artifact Store',
    blurb:
      'Open-source shared artifact store for multi-agent systems. Passes a 12-byte ID instead of full payloads between LangGraph agents — cuts context-window bloat without losing data fidelity.',
    href: 'https://github.com/Himeshxx04/mcp-artifact-store',
    stack: ['FastAPI', 'FastMCP', 'PostgreSQL', 'LangGraph'],
    icon: 'network',
  },
  {
    title: 'RAG Pipeline Optimizer',
    blurb:
      'Production RAG that generates multiple candidates, scores them with an LLM judge on quality / grounding / cost / latency, and picks the winner. Tunable quality–cost–latency tradeoff.',
    href: 'https://github.com/Himeshxx04/rag-pipeline-optimizer',
    stack: ['FastAPI', 'FAISS', 'OpenAI', 'React'],
    icon: 'database',
  },
]

export function FeaturedProjects() {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="text-[10px] font-medium uppercase tracking-[0.22em] text-ink-dim">
          Featured Work
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wider text-ink-dim">
          2 of 8
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {PROJECTS.map((p) => (
          <a
            key={p.title}
            href={p.href}
            target="_blank"
            rel="noreferrer"
            className="glass glass-hover group relative flex flex-col gap-3 rounded-xl p-4"
          >
            <div className="flex items-start justify-between">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10 ring-1 ring-accent/20">
                {p.icon === 'network' ? (
                  <Network className="h-4 w-4 text-accent" />
                ) : (
                  <Database className="h-4 w-4 text-accent" />
                )}
              </div>
              <ArrowUpRight className="h-4 w-4 text-ink-dim transition-all group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-ink" />
            </div>

            <div>
              <h3 className="text-[15px] font-semibold text-ink">{p.title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-muted">
                {p.blurb}
              </p>
            </div>

            <div className="mt-auto flex flex-wrap gap-1.5">
              {p.stack.map((s) => (
                <span
                  key={s}
                  className="rounded-sm border border-white/10 bg-white/[0.02] px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-dim"
                >
                  {s}
                </span>
              ))}
            </div>
          </a>
        ))}
      </div>
    </section>
  )
}
