/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'sans-serif',
        ],
        mono: [
          'JetBrains Mono',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'Consolas',
          'monospace',
        ],
        display: [
          'Instrument Serif',
          'ui-serif',
          'Georgia',
          'serif',
        ],
      },
      colors: {
        canvas:   '#07070b',
        surface:  '#0e0e15',
        elevated: '#15151f',
        border:   '#22222d',
        ink: {
          DEFAULT: '#f4f4f6',
          muted:   '#a1a1ac',
          dim:     '#62626c',
        },
        accent: {
          DEFAULT: '#34d399',
          hover:   '#10b981',
          dim:     '#064e3b',
        },
        // Companion hue for the gradient family
        teal: {
          400: '#2dd4bf',
          500: '#14b8a6',
        },
        cyan: {
          400: '#22d3ee',
        },
      },
      backgroundImage: {
        'dot-grid': "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.045) 1px, transparent 0)",
        // Hero spotlight: a vertical fade with a hint of emerald
        'spotlight': "radial-gradient(ellipse 90% 55% at 50% -10%, rgba(52,211,153,0.10), transparent 65%)",
        // Card surface gradient — gives glass cards subtle vertical depth
        'card': "linear-gradient(180deg, rgba(255,255,255,0.025) 0%, rgba(255,255,255,0.0) 100%)",
        // Gradient text for the name
        'name-gradient': "linear-gradient(180deg, #ffffff 0%, #a1a1ac 100%)",
        // Emerald → teal blend for accents
        'accent-blend': "linear-gradient(135deg, #34d399 0%, #2dd4bf 50%, #22d3ee 100%)",
      },
      backgroundSize: {
        'grid-32': '32px 32px',
      },
      boxShadow: {
        // Soft, layered shadow for floating cards
        'card':       '0 1px 0 0 rgba(255,255,255,0.04) inset, 0 1px 30px -8px rgba(0,0,0,0.5)',
        'card-hover': '0 1px 0 0 rgba(255,255,255,0.06) inset, 0 8px 40px -8px rgba(52,211,153,0.12)',
        // Big CTA button glow
        'glow-emerald': '0 0 0 1px rgba(52,211,153,0.4), 0 8px 48px -8px rgba(52,211,153,0.5), inset 0 1px 0 0 rgba(255,255,255,0.1)',
        'glow-soft':    '0 0 0 1px rgba(52,211,153,0.25), 0 8px 32px -10px rgba(52,211,153,0.25)',
      },
      animation: {
        'pulse-soft':  'pulse-soft 2.6s ease-in-out infinite',
        'pulse-dot':   'pulse-dot 2.2s ease-in-out infinite',
        'message-in':  'message-in 280ms cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-in':     'fade-in 500ms ease-out',
        'aurora-1':    'aurora-1 28s ease-in-out infinite',
        'aurora-2':    'aurora-2 32s ease-in-out infinite',
        'rise':        'rise 600ms cubic-bezier(0.16, 1, 0.3, 1)',
      },
      keyframes: {
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0.55' },
        },
        'pulse-dot': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(52,211,153,0.5)' },
          '70%':      { boxShadow: '0 0 0 8px rgba(52,211,153,0)' },
        },
        'message-in': {
          '0%':   { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'rise': {
          '0%':   { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        // Slow drifting aurora blobs in the background
        'aurora-1': {
          '0%, 100%': { transform: 'translate(-10%, -10%) scale(1)' },
          '50%':      { transform: 'translate(8%, 10%) scale(1.1)' },
        },
        'aurora-2': {
          '0%, 100%': { transform: 'translate(10%, 5%) scale(1.05)' },
          '50%':      { transform: 'translate(-8%, -8%) scale(0.95)' },
        },
      },
    },
  },
  plugins: [],
}
