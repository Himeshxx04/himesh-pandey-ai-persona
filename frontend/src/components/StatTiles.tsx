import { Calendar, Code2, Cpu, GitBranch } from 'lucide-react'

interface Stat {
  label: string
  value: string
  sub: string
  icon: 'cpu' | 'git' | 'code' | 'cal'
  tint: 'emerald' | 'teal' | 'cyan' | 'neutral'
}

const STATS: Stat[] = [
  {
    label: 'Deployed AI systems',
    value: '2',
    sub: 'Production · open-source',
    icon: 'cpu',
    tint: 'emerald',
  },
  {
    label: 'Open-source release',
    value: 'MCP',
    sub: 'Artifact Store · live',
    icon: 'git',
    tint: 'teal',
  },
  {
    label: 'DSA problems solved',
    value: '300+',
    sub: 'C++ · competitive prog.',
    icon: 'code',
    tint: 'cyan',
  },
  {
    label: 'Graduating',
    value: 'May 2026',
    sub: 'ECE · PES University',
    icon: 'cal',
    tint: 'neutral',
  },
]

const ICON: Record<Stat['icon'], typeof Cpu> = {
  cpu:  Cpu,
  git:  GitBranch,
  code: Code2,
  cal:  Calendar,
}

const TINT: Record<Stat['tint'], { bg: string; text: string; ring: string }> = {
  emerald: { bg: 'bg-emerald-500/10',  text: 'text-emerald-300',  ring: 'ring-emerald-400/25' },
  teal:    { bg: 'bg-teal-500/10',     text: 'text-teal-300',     ring: 'ring-teal-400/25' },
  cyan:    { bg: 'bg-cyan-500/10',     text: 'text-cyan-300',     ring: 'ring-cyan-400/25' },
  neutral: { bg: 'bg-white/5',         text: 'text-ink',          ring: 'ring-white/10' },
}

export function StatTiles() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {STATS.map((s) => {
        const Icon = ICON[s.icon]
        const t = TINT[s.tint]
        return (
          <div
            key={s.label}
            className="glass glass-hover group flex flex-col gap-3 rounded-xl p-4"
          >
            <div className="flex items-center justify-between">
              <span className={`flex h-8 w-8 items-center justify-center rounded-lg ring-1 ${t.bg} ${t.ring}`}>
                <Icon className={`h-4 w-4 ${t.text}`} />
              </span>
              <span className="text-[9px] font-medium uppercase tracking-[0.18em] text-ink-dim">
                {s.label}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <div className={`text-[1.6rem] font-semibold leading-none tracking-tight ${t.text}`}>
                {s.value}
              </div>
              <div className="text-[12px] text-ink-dim">{s.sub}</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
