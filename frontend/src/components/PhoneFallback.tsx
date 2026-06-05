import { Check, Copy, Phone, PhoneIncoming, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { requestCallback } from '../lib/api'

const NUMBER = '+1 (937) 888-3660'
const TEL = '+19378883660'

type Status =
  | { state: 'idle' }
  | { state: 'submitting' }
  | { state: 'success'; message: string }
  | { state: 'error'; message: string }

/**
 * Two paths into the phone channel, both inside one glass card:
 *   1. PRIMARY — outbound callback. User types their number; backend asks
 *      Twilio to dial them; Twilio bridges to LiveKit on answer.
 *      Solves the international-calling-from-India problem entirely.
 *   2. SECONDARY — the inbound US number, for evaluators with ISD enabled
 *      or anyone who'd rather dial in themselves.
 */
export function PhoneFallback() {
  const [country, setCountry] = useState<'+91' | '+1'>('+91')
  const [local, setLocal] = useState('')
  const [status, setStatus] = useState<Status>({ state: 'idle' })
  const [copied, setCopied] = useState(false)

  async function copyNumber() {
    try {
      await navigator.clipboard.writeText(TEL)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard blocked — silently ignore */
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const digits = local.replace(/[^\d]/g, '')
    if (!digits) {
      setStatus({ state: 'error', message: 'Enter a phone number.' })
      return
    }
    setStatus({ state: 'submitting' })
    try {
      const res = await requestCallback(`${country}${digits}`)
      setStatus({ state: 'success', message: res.message })
    } catch (err) {
      setStatus({ state: 'error', message: (err as Error).message })
    }
  }

  return (
    <div className="glass relative flex flex-col gap-5 rounded-2xl p-5 sm:p-6">
      {/* ── Primary: have the agent call you ─────────────────── */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-ink-muted">
          <PhoneIncoming className="h-3.5 w-3.5 text-accent" />
          Have the agent call you
        </div>

        <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
          {/* Country selector */}
          <div className="relative">
            <select
              value={country}
              onChange={(e) => setCountry(e.target.value as '+91' | '+1')}
              disabled={status.state === 'submitting'}
              className="h-full appearance-none rounded-lg border border-white/10 bg-white/[0.02] py-3 pl-3 pr-7 font-mono text-sm text-ink transition-colors hover:border-white/20 focus:border-accent/40 focus:outline-none focus:ring-1 focus:ring-accent/20"
            >
              <option value="+91">+91</option>
              <option value="+1">+1</option>
            </select>
            <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-ink-dim">
              ▾
            </span>
          </div>

          {/* Local number */}
          <input
            type="tel"
            inputMode="numeric"
            placeholder={country === '+91' ? '98765 43210' : '415 555 1234'}
            value={local}
            onChange={(e) => setLocal(e.target.value)}
            disabled={status.state === 'submitting'}
            className="flex-1 rounded-lg border border-white/10 bg-white/[0.02] px-3.5 py-3 font-mono text-sm text-ink placeholder:text-ink-dim transition-colors focus:border-accent/40 focus:bg-white/[0.04] focus:outline-none focus:ring-1 focus:ring-accent/20 disabled:opacity-60"
          />

          <button
            type="submit"
            disabled={status.state === 'submitting' || !local.trim()}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-accent/40 bg-accent/[0.08] px-4 py-3 text-sm font-medium text-accent transition-colors hover:border-accent hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {status.state === 'submitting' ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Dialing
              </>
            ) : (
              <>Call me</>
            )}
          </button>
        </form>

        {/* Status row */}
        {status.state === 'success' && (
          <div className="flex items-start gap-2 rounded-md border border-accent/30 bg-accent/[0.05] px-3 py-2 text-[13px] text-accent">
            <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{status.message}</span>
          </div>
        )}
        {status.state === 'error' && (
          <p className="rounded-md border border-red-500/30 bg-red-500/5 px-3 py-2 text-[13px] text-red-400">
            {status.message}
          </p>
        )}
        {status.state === 'idle' && (
          <p className="text-[11px] leading-relaxed text-ink-dim">
            Works from any phone — no international calling needed. We dial you;
            you answer; the agent picks up. India & US numbers supported.
          </p>
        )}
      </div>

      <div className="border-t border-white/[0.06]" />

      {/* ── Secondary: direct inbound number ─────────────────── */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] text-ink-muted">
            <Phone className="h-3.5 w-3.5" />
            Or dial directly
          </div>
          <button
            type="button"
            onClick={copyNumber}
            className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.02] px-2 py-1 text-[11px] text-ink-muted transition-colors hover:border-white/20 hover:text-ink"
          >
            {copied ? (
              <>
                <Check className="h-3 w-3 text-accent" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" />
                Copy
              </>
            )}
          </button>
        </div>
        <a
          href={`tel:${TEL}`}
          className="font-mono text-lg text-ink transition-colors hover:text-accent"
        >
          {NUMBER}
        </a>
        <p className="text-[11px] leading-relaxed text-ink-dim">
          US number. Requires international dialing on your line.
        </p>
      </div>

      {/* Subtle corner glow */}
      <div
        className="pointer-events-none absolute -right-12 -bottom-12 h-32 w-32 rounded-full opacity-25 blur-2xl"
        style={{ background: 'radial-gradient(circle, #34d399 0%, transparent 70%)' }}
        aria-hidden
      />
    </div>
  )
}
