export function SectionHeading({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <div className="mb-3">
      <div className="flex items-baseline gap-3">
        <h2 className="text-[11px] font-medium uppercase tracking-[0.14em] text-neutral-500">
          {children}
        </h2>
        <span className="h-px flex-1 bg-white/[0.06]" />
        {hint && <span className="shrink-0 text-[11px] text-neutral-600">{hint}</span>}
      </div>
    </div>
  )
}
