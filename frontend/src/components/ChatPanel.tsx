import { useEffect, useRef, useState } from 'react'
import { ArrowUp } from 'lucide-react'
import { askStream, type HistoryMessage, type BookingInfo } from '../lib/api'
import { Message, type MessageData } from './Message'

const SUGGESTIONS = [
  'Tell me about the MCP Artifact Store.',
  'Why are you the right fit for an AI Engineer role?',
  'What did you do at your internship?',
  'Are you free this week?',
]

/**
 * Chat panel with token-by-token SSE streaming. Empty-state surfaces
 * quick-start prompts; live state shows a streaming cursor on the
 * in-flight assistant message.
 */
export function ChatPanel() {
  const [messages, setMessages] = useState<MessageData[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // smooth-scroll to bottom whenever the thread changes
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, streaming])

  // cancel any in-flight stream on unmount
  useEffect(() => () => abortRef.current?.abort(), [])

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || streaming) return

    setInput('')
    setError(null)

    // Snapshot history excluding the new user message
    const history: HistoryMessage[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }))

    // Append user message + an empty assistant placeholder that we'll
    // grow as tokens arrive.
    const userMsg: MessageData = { role: 'user', content: trimmed }
    const placeholder: MessageData = {
      role: 'assistant',
      content: '',
      streaming: true,
    }
    setMessages((prev) => [...prev, userMsg, placeholder])
    setStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      await askStream(trimmed, history, {
        signal: controller.signal,
        onSources: (sources) => {
          setMessages((prev) => {
            const copy = [...prev]
            const last = copy[copy.length - 1]
            if (last && last.role === 'assistant') {
              copy[copy.length - 1] = { ...last, sources }
            }
            return copy
          })
        },
        onToken: (text) => {
          setMessages((prev) => {
            const copy = [...prev]
            const last = copy[copy.length - 1]
            if (last && last.role === 'assistant') {
              copy[copy.length - 1] = {
                ...last,
                content: last.content + text,
              }
            }
            return copy
          })
        },
        onDone: ({ booking }: { booking?: BookingInfo | null }) => {
          setMessages((prev) => {
            const copy = [...prev]
            const last = copy[copy.length - 1]
            if (last && last.role === 'assistant') {
              copy[copy.length - 1] = {
                ...last,
                streaming: false,
                bookingNotice: booking?.confirmation_message,
              }
            }
            return copy
          })
        },
        onError: (m) => setError(m),
      })
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        setError((e as Error).message)
      }
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }

  function stop() {
    abortRef.current?.abort()
    // Mark the last assistant message as done
    setMessages((prev) => {
      const copy = [...prev]
      const last = copy[copy.length - 1]
      if (last && last.role === 'assistant' && last.streaming) {
        copy[copy.length - 1] = { ...last, streaming: false }
      }
      return copy
    })
  }

  return (
    <section className="glass flex min-h-[640px] flex-col rounded-2xl p-5 sm:p-7">
      {/* Section header */}
      <div className="flex items-center justify-between border-b border-white/[0.06] pb-4">
        <div className="flex items-center gap-2.5">
          <span className="relative inline-block h-2 w-2">
            <span className="absolute inset-0 rounded-full bg-accent" />
            <span className="absolute inset-0 rounded-full bg-accent animate-pulse-dot" />
          </span>
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.22em] text-ink">
            Live Chat
          </h2>
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wider text-ink-dim">
          {Math.floor(messages.length / 2)} turn{messages.length === 2 ? '' : 's'}
        </span>
      </div>

      {/* Messages area — grows to fill, scrolls when content overflows */}
      <div className="flex flex-1 flex-col gap-6 overflow-y-auto py-5">
        {messages.length === 0 ? (
          <div className="flex flex-col gap-4">
            <p className="text-[15px] leading-relaxed text-ink-muted">
              Hey — I'm Himesh's AI representative. I answer from his resume
              and GitHub. Ask me about projects, internship, availability, or
              anything else. A few starters:
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => send(s)}
                  className="rounded-md border border-white/10 bg-white/[0.02] px-3 py-1.5 text-sm text-ink-muted transition-all hover:border-accent/40 hover:bg-white/[0.04] hover:text-ink"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((m, i) => (
              <Message key={i} msg={m} />
            ))}
            <div ref={endRef} />
          </>
        )}
      </div>

      {error && (
        <p className="rounded-md border border-red-500/30 bg-red-500/5 px-3 py-2 text-sm text-red-400">
          {error}
        </p>
      )}

      {/* Composer — sits flush at the bottom of the panel */}
      <form
        className="flex items-end gap-2.5 border-t border-white/[0.06] pt-4"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <div className="relative flex-1">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send(input)
              }
            }}
            placeholder="Ask anything about Himesh…"
            rows={1}
            disabled={streaming}
            className="w-full resize-none rounded-lg border border-white/10 bg-white/[0.025] px-4 py-3.5 text-[15px] text-ink placeholder:text-ink-dim transition-all focus:border-accent/50 focus:bg-white/[0.04] focus:outline-none focus:ring-2 focus:ring-accent/15 disabled:opacity-60"
          />
        </div>
        {streaming ? (
          <button
            type="button"
            onClick={stop}
            className="flex h-12 w-12 items-center justify-center rounded-lg border border-red-500/30 bg-red-500/10 text-red-400 transition-colors hover:bg-red-500/20"
            aria-label="Stop streaming"
            title="Stop"
          >
            <span className="block h-3 w-3 rounded-sm bg-red-400" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className="flex h-12 w-12 items-center justify-center rounded-lg border border-accent/50 bg-accent text-canvas shadow-glow-soft transition-all hover:bg-accent-hover hover:shadow-glow-emerald disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/[0.05] disabled:text-ink-dim disabled:shadow-none"
            aria-label="Send"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        )}
      </form>
    </section>
  )
}
