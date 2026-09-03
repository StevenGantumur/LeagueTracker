"use client"

import { useState } from "react"
import { signed, type WinFactor, type WinFactors } from "../lib/api"
import { SectionHeading } from "./SectionHeading"

const GROUPS = [
  { id: "team", heading: "Whole team", note: "Both teams summed — the state of the map." },
  { id: "personal", heading: "Your lane", note: "You against the player opposite you." },
  { id: "role", heading: "Lane by lane", note: "Each matchup on its own." },
]

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      viewBox="0 0 12 12"
      aria-hidden
      className={`h-3 w-3 shrink-0 text-neutral-600 transition-transform duration-150 group-hover:text-neutral-300 ${
        open ? "rotate-90" : ""
      }`}
    >
      <path d="M4 2.5 L8 6 L4 9.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function Factor({ factor, scale }: { factor: WinFactor; scale: number }) {
  const [open, setOpen] = useState(false)
  const d = factor.effect_size ?? 0
  const width = Math.min(100, (Math.abs(d) / scale) * 100)

  return (
    <div className="border-b border-white/[0.06] last:border-0">
      <button
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
        className="group relative w-full cursor-pointer py-3.5 text-left"
      >
        <div className="flex items-baseline gap-3">
          <span className="self-center">
            <Chevron open={open} />
          </span>

          <span className="flex-1 text-[15px] text-neutral-200 transition-colors group-hover:text-white">
            {factor.label.replace(` at ${factor.minute} min`, "")}
            <span className="tabular ml-2 text-[11px] text-neutral-600">{factor.minute}′</span>
          </span>

          <span className="tabular w-24 text-right text-[13px] text-emerald-300/80">
            {signed(factor.win_avg, factor.unit)}
          </span>
          <span className="tabular w-24 text-right text-[13px] text-rose-300/70">
            {signed(factor.loss_avg, factor.unit)}
          </span>
          <span className="tabular w-14 text-right text-[13px] text-neutral-400">
            {d.toFixed(2)}
          </span>
        </div>

        {/* Hairline whose length encodes the effect size — the bar chart, minus the chart. */}
        <span
          className="absolute bottom-0 left-0 h-px bg-white/25 transition-all"
          style={{ width: `${width}%` }}
        />
      </button>

      {open && (
        <p className="mb-4 ml-6 max-w-prose border-l border-white/10 pl-4 text-[13.5px] leading-relaxed text-neutral-400">
          {factor.tip}
        </p>
      )}
    </div>
  )
}

export function WinFactorsPanel({ data }: { data: WinFactors }) {
  const scale = Math.max(...data.factors.map(f => Math.abs(f.effect_size ?? 0)), 0.01)

  return (
    <section className="mt-12">
      <SectionHeading hint="click a row for what to do about it">What shows up in wins</SectionHeading>

      <div className="mb-6 flex items-baseline gap-3 pl-6 text-[11px] text-neutral-600">
        <span className="flex-1" />
        <span className="tabular w-24 text-right">won</span>
        <span className="tabular w-24 text-right">lost</span>
        <span className="tabular w-14 text-right">d</span>
      </div>

      {GROUPS.map(group => {
        const rows = data.factors.filter(f => f.group === group.id)
        if (rows.length === 0) return null
        return (
          <div key={group.id} className="mb-9">
            <div className="mb-1 flex items-baseline gap-3">
              <h3 className="text-[11px] font-medium uppercase tracking-[0.14em] text-neutral-500">
                {group.heading}
              </h3>
              <span className="h-px flex-1 bg-white/[0.06]" />
            </div>
            <p className="mb-2 text-[12.5px] text-neutral-600">{group.note}</p>
            {rows.map(f => (
              <Factor key={f.metric} factor={f} scale={scale} />
            ))}
          </div>
        )
      })}

      <p className="max-w-prose text-[12.5px] leading-relaxed text-neutral-600">{data.note}</p>
    </section>
  )
}
