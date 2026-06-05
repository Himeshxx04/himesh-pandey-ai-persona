/**
 * Background blob field. Two slow-drifting radial gradients (emerald + cyan)
 * give the canvas subtle depth and movement without distracting. Pointer-
 * events disabled so they never block clicks.
 */
export function Aurora() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* Top-left emerald blob */}
      <div
        className="absolute -left-32 -top-32 h-[640px] w-[640px] rounded-full opacity-[0.18] blur-3xl animate-aurora-1"
        style={{
          background:
            'radial-gradient(circle at 30% 30%, #34d399 0%, transparent 60%)',
        }}
        aria-hidden
      />
      {/* Top-right cyan blob */}
      <div
        className="absolute -right-32 top-32 h-[520px] w-[520px] rounded-full opacity-[0.14] blur-3xl animate-aurora-2"
        style={{
          background:
            'radial-gradient(circle at 70% 50%, #22d3ee 0%, transparent 60%)',
        }}
        aria-hidden
      />
      {/* Lower-middle teal blob */}
      <div
        className="absolute bottom-0 left-1/3 h-[480px] w-[480px] rounded-full opacity-[0.08] blur-3xl animate-aurora-1"
        style={{
          background:
            'radial-gradient(circle at 50% 50%, #2dd4bf 0%, transparent 60%)',
          animationDelay: '-12s',
        }}
        aria-hidden
      />

      {/* Dot grid layer (very subtle texture) */}
      <div className="absolute inset-0 bg-dot-grid bg-grid-32 opacity-40" />

      {/* Top spotlight that anchors the hero */}
      <div className="absolute inset-x-0 top-0 h-[560px] bg-spotlight" />
    </div>
  )
}
