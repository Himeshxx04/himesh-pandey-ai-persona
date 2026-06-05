import { useEffect, useState } from 'react'
import { FileText } from 'lucide-react'

interface Script {
  user: string
  assistant: string
  sources: string[]
}

/**
 * Hero visual hook. Auto-types a sample chat conversation (user prompt →
 * streamed assistant reply with source chips) and loops through three
 * scripts. Demonstrates what the page DOES on first paint — visitors
 * see streaming + grounded answers before scrolling.
 */

const SCRIPTS: Script[] = [
  {
    user: 'Tell me about your MCP Artifact Store.',
    assistant:
      'Open-source artifact store for multi-agent systems. Agents pass a 12-byte ID instead of full payloads — cuts context-window bloat without losing data fidelity.',
    sources: ['mcp-store/readme', 'about_me'],
  },
  {
    user: 'Are you free this Wednesday?',
    assistant:
      "Checking my calendar… Wednesday at 11 AM and 3 PM IST are open. Want me to lock one in? I'll need your name and email.",
    sources: ['cal.com/availability'],
  },
  {
    user: "What's your biggest weakness?",
    assistant:
      'I try to learn everything at once when picking up a new area. I manage it by scoping aggressively — especially under deadline.',
    sources: ['about_me'],
  },
]

type Phase = 'typing-user' | 'pause-mid' | 'streaming-assistant' | 'pause-end' | 'reset'

const SPEED_USER       = 28    // ms per char while typing user
const SPEED_ASSISTANT  = 18    // ms per char while streaming reply
const PAUSE_MID_MS     = 550   // pause between user finishing and assistant starting
const PAUSE_END_MS     = 3200  // pause after reply completes before next script
const RESET_DELAY_MS   = 350   // small clear before next script

export function MockChatPreview() {
  const [scriptIdx, setScriptIdx] = useState(0)
  const [userText, setUserText] = useState('')
  const [assistantText, setAssistantText] = useState('')
  const [showSources, setShowSources] = useState(false)
  const [phase, setPhase] = useState<Phase>('typing-user')

  useEffect(() => {
    const script = SCRIPTS[scriptIdx]

    if (phase === 'typing-user') {
      if (userText.length < script.user.length) {
        const t = window.setTimeout(
          () => setUserText(script.user.slice(0, userText.length + 1)),
          SPEED_USER,
        )
        return () => window.clearTimeout(t)
      }
      const t = window.setTimeout(() => setPhase('pause-mid'), 350)
      return () => window.clearTimeout(t)
    }

    if (phase === 'pause-mid') {
      const t = window.setTimeout(() => setPhase('streaming-assistant'), PAUSE_MID_MS)
      return () => window.clearTimeout(t)
    }

    if (phase === 'streaming-assistant') {
      if (assistantText.length < script.assistant.length) {
        const t = window.setTimeout(
          () => setAssistantText(script.assistant.slice(0, assistantText.length + 1)),
          SPEED_ASSISTANT,
        )
        return () => window.clearTimeout(t)
      }
      setShowSources(true)
      const t = window.setTimeout(() => setPhase('pause-end'), PAUSE_END_MS)
      return () => window.clearTimeout(t)
    }

    if (phase === 'pause-end') {
      const t = window.setTimeout(() => setPhase('reset'), 200)
      return () => window.clearTimeout(t)
    }

    if (phase === 'reset') {
      const t = window.setTimeout(() => {
        setUserText('')
        setAssistantText('')
        setShowSources(false)
        setScriptIdx((idx) => (idx + 1) % SCRIPTS.length)
        setPhase('typing-user')
      }, RESET_DELAY_MS)
      return () => window.clearTimeout(t)
    }
  }, [phase, userText, assistantText, scriptIdx])

  const script = SCRIPTS[scriptIdx]
  const showAssistant =
    phase === 'streaming-assistant' || phase === 'pause-end' || assistantText.length > 0

  return (
    <div className="glass relative flex flex-col overflow-hidden rounded-2xl p-5 sm:p-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
        <div className="flex items-center gap-2.5">
          <span className="relative inline-block h-2 w-2">
            <span className="absolute inset-0 rounded-full bg-accent" />
            <span className="absolute inset-0 rounded-full bg-accent animate-pulse-dot" />
          </span>
          <span className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ink">
            Live Preview
          </span>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wider text-ink-dim">
          streaming · grounded
        </span>
      </div>

      {/* Conversation */}
      <div className="mt-5 flex min-h-[280px] flex-col gap-5">
        {/* User turn */}
        <div className="flex flex-col gap-1.5">
          <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-ink-dim">
            You
          </div>
          <div className="text-[14px] leading-relaxed text-ink">
            {userText}
            {phase === 'typing-user' && (
              <Cursor color="ink-muted" />
            )}
          </div>
        </div>

        {/* Assistant turn (revealed only after user finishes) */}
        {showAssistant && (
          <div className="flex flex-col gap-1.5">
            <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-ink-dim">
              Himesh
            </div>
            <div className="border-l border-accent/40 pl-3 text-[14px] leading-relaxed text-ink">
              {assistantText}
              {phase === 'streaming-assistant' && <Cursor color="accent" />}
            </div>
            {showSources && (
              <div className="ml-3 mt-1.5 flex flex-wrap gap-1.5 animate-fade-in">
                {script.sources.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1 rounded border border-white/10 bg-white/[0.02] px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-muted"
                  >
                    <FileText className="h-2.5 w-2.5" />
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Soft corner glow */}
      <div
        className="pointer-events-none absolute -right-16 -bottom-16 h-40 w-40 rounded-full opacity-25 blur-2xl"
        style={{ background: 'radial-gradient(circle, #34d399 0%, transparent 70%)' }}
        aria-hidden
      />
    </div>
  )
}

function Cursor({ color }: { color: 'accent' | 'ink-muted' }) {
  const cls =
    color === 'accent'
      ? 'bg-accent'
      : 'bg-ink-muted'
  return (
    <span
      className={
        'ml-0.5 inline-block h-3.5 w-[2px] -mb-0.5 align-middle animate-pulse-soft ' + cls
      }
      aria-hidden
    />
  )
}
