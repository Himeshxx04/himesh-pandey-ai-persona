import { ExternalLink, Mail, MapPin } from 'lucide-react'
import { GithubIcon, LinkedinIcon } from './BrandIcons'

/**
 * Compact intro section. Single-screen scannable: status pill, name,
 * one-sentence value prop, and three functional contact links
 * (GitHub, LinkedIn, email). All links open in a new tab.
 */
export function Hero() {
  return (
    <header className="flex flex-col gap-7 animate-rise">
      <div className="flex flex-wrap items-center gap-3">
        <div className="glass inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] text-ink-muted">
          <MapPin className="h-3 w-3" />
          Bengaluru · IST
        </div>
      </div>

      <div className="flex flex-col gap-5">
        <p className="text-[11px] uppercase tracking-[0.28em]">
          <span className="accent-text font-semibold">AI Representative</span>
          <span className="ml-3 text-ink-dim">— for Himesh Pandey</span>
        </p>

        <h1 className="font-display text-[4rem] font-normal leading-[0.96] tracking-[-0.025em] sm:text-[5rem]">
          <span className="name-gradient">Himesh</span>
          <br />
          <span className="name-gradient">Pandey.</span>
        </h1>

        <p className="max-w-[36rem] text-[17px] leading-[1.55] text-ink-muted">
          B.Tech grad building production-grade agentic systems. This page
          is my AI representative — ask it anything about my background,
          projects, or availability. It books real calls on my calendar.
        </p>
      </div>

      {/* Functional link row — every item navigates somewhere */}
      <div className="flex flex-wrap gap-2.5">
        <ContactLink
          href="https://github.com/Himeshxx04"
          icon={<GithubIcon className="h-4 w-4" />}
          label="GitHub"
          handle="@Himeshxx04"
        />
        <ContactLink
          href="https://linkedin.com/in/himesh-pandey-66968a213"
          icon={<LinkedinIcon className="h-4 w-4" />}
          label="LinkedIn"
          handle="himesh-pandey"
        />
        <ContactLink
          href="mailto:pandeyhimesh09@gmail.com"
          icon={<Mail className="h-4 w-4" />}
          label="Email"
          handle="pandeyhimesh09@gmail.com"
          external={false}
        />
      </div>
    </header>
  )
}

function ContactLink({
  href,
  icon,
  label,
  handle,
  external = true,
}: {
  href: string
  icon: React.ReactNode
  label: string
  handle: string
  external?: boolean
}) {
  return (
    <a
      href={href}
      target={external ? '_blank' : undefined}
      rel={external ? 'noreferrer' : undefined}
      className="glass glass-hover group inline-flex items-center gap-3 rounded-lg px-3.5 py-2"
    >
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-white/[0.04] text-ink-muted transition-colors group-hover:bg-accent/10 group-hover:text-accent">
        {icon}
      </span>
      <span className="flex flex-col">
        <span className="text-[10px] font-medium uppercase tracking-[0.15em] text-ink-dim">
          {label}
        </span>
        <span className="font-mono text-[12px] text-ink">{handle}</span>
      </span>
      {external && (
        <ExternalLink className="ml-1 h-3.5 w-3.5 text-ink-dim transition-all group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-ink" />
      )}
    </a>
  )
}
