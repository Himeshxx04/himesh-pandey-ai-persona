import { FileText } from 'lucide-react'

export interface MessageData {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  bookingNotice?: string
  streaming?: boolean
}

/**
 * One message in the thread. Distinct user vs assistant typography
 * (no avatar circles); assistant gets a thin accent edge while
 * streaming.
 */
export function Message({ msg }: { msg: MessageData }) {
  const isUser = msg.role === 'user'

  return (
    <div className="group relative flex flex-col gap-2 animate-message-in">
      <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-ink-dim">
        {isUser ? 'You' : 'Himesh'}
      </div>

      <div
        className={
          'whitespace-pre-wrap text-[15px] leading-relaxed text-ink ' +
          (isUser ? '' : 'pl-4 border-l border-border/60')
        }
      >
        {msg.content}
        {msg.streaming && (
          <span
            className="ml-0.5 inline-block h-4 w-[2px] translate-y-[3px] bg-accent animate-pulse-soft"
            aria-hidden
          />
        )}
      </div>

      {msg.sources && msg.sources.length > 0 && !msg.streaming && (
        <div className="ml-4 flex flex-wrap gap-1.5 pt-1">
          {msg.sources.map((src) => (
            <span
              key={src}
              className="inline-flex items-center gap-1 rounded border border-border bg-surface px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-muted"
              title={`Retrieved from ${src}`}
            >
              <FileText className="h-2.5 w-2.5" />
              {src}
            </span>
          ))}
        </div>
      )}

      {msg.bookingNotice && (
        <div className="ml-4 mt-1 rounded-md border border-accent/30 bg-accent/5 px-3 py-2.5 text-sm text-accent">
          <span className="mr-1 font-semibold">✓ Booked.</span>
          {msg.bookingNotice}
        </div>
      )}
    </div>
  )
}
