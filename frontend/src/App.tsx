import { Aurora } from './components/Aurora'
import { CallButton } from './components/CallButton'
import { ChatPanel } from './components/ChatPanel'
import { FeaturedProjects } from './components/FeaturedProjects'
import { Hero } from './components/Hero'
import { MockChatPreview } from './components/MockChatPreview'
import { PhoneFallback } from './components/PhoneFallback'
import { TechStack } from './components/TechStack'

/**
 * Single-page narrative — scroll order matches reading order:
 *   1. Hero            (who, what, contact)
 *   2. Tech stack      (what I build with)
 *   3. Featured work   (clickable project cards → GitHub)
 *   4. Voice call      (web call CTA + phone fallback)
 *   5. Chat            (primary deliverable — large)
 *
 * Every clickable element actually navigates or does something. No
 * decorative stat tiles. No vibe-coded badges.
 */
function App() {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <Aurora />

      <main className="relative mx-auto max-w-[1200px] px-5 pb-12 pt-12 sm:px-8 sm:pt-16">
        {/* ── 1. Hero — identity left, live preview right ─────── */}
        <section className="grid items-start gap-10 lg:grid-cols-[minmax(0,_1fr)_minmax(0,_0.9fr)] lg:gap-12">
          <Hero />
          <div
            className="lg:mt-2 animate-rise"
            style={{ animationDelay: '120ms' }}
          >
            <MockChatPreview />
          </div>
        </section>

        {/* ── 2. Tech stack ─────────────────────────────────────── */}
        <section
          className="mt-20 animate-rise"
          style={{ animationDelay: '80ms' }}
        >
          <SectionLabel num="01" label="What I build with" />
          <TechStack />
        </section>

        {/* ── 3. Featured work ──────────────────────────────────── */}
        <section
          className="mt-16 animate-rise"
          style={{ animationDelay: '140ms' }}
        >
          <SectionLabel num="02" label="Featured work" hint="Click any card →" />
          <FeaturedProjects />
        </section>

        {/* ── 4. Voice call ─────────────────────────────────────── */}
        <section
          className="mt-16 animate-rise"
          style={{ animationDelay: '180ms' }}
        >
          <SectionLabel num="03" label="Talk to the agent" />
          <div className="grid gap-4 lg:grid-cols-[minmax(0,_1.3fr)_minmax(0,_1fr)] lg:gap-5">
            <CallButton />
            <PhoneFallback />
          </div>
        </section>

        {/* ── 5. Chat (primary deliverable — most real estate) ──── */}
        <section
          className="mt-16 animate-rise"
          style={{ animationDelay: '220ms' }}
        >
          <SectionLabel num="04" label="Or chat with me" hint="Streamed answers · grounded in resume + GitHub" />
          <ChatPanel />
        </section>
      </main>

      <footer className="relative border-t border-white/[0.04] px-6 py-8 text-center text-[11px] text-ink-dim">
        © {new Date().getFullYear()} Himesh Pandey · pandeyhimesh09@gmail.com
      </footer>
    </div>
  )
}

function SectionLabel({
  num,
  label,
  hint,
}: {
  num: string
  label: string
  hint?: string
}) {
  return (
    <div className="mb-5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-ink-dim">
          {num}
        </span>
        <h2 className="text-[15px] font-semibold tracking-tight text-ink">
          {label}
        </h2>
      </div>
      {hint && (
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-dim">
          {hint}
        </span>
      )}
    </div>
  )
}

export default App
