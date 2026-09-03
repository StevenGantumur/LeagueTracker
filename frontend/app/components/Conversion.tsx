"use client"

import { percent, type Conversion } from "../lib/api"
import { SectionHeading } from "./SectionHeading"

function Side({
  text,
  games,
  rate,
  tone,
}: {
  text: string
  games: number
  rate: number | null
  tone: "up" | "down"
}) {
  return (
    <div className="flex-1">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="text-[12.5px] text-neutral-400">{text}</span>
        <span className="tabular text-[11px] text-neutral-600">{games}g</span>
      </div>
      <div
        className={`tabular text-[26px] font-medium tracking-tight ${
          tone === "up" ? "text-emerald-300/90" : "text-rose-300/70"
        }`}
      >
        {percent(rate)}
      </div>
      {/* A proportional rule reads faster than the number alone. */}
      <div className="mt-2 h-px w-full bg-white/[0.07]">
        <div
          className={`h-px ${tone === "up" ? "bg-emerald-300/60" : "bg-rose-300/40"}`}
          style={{ width: `${(rate ?? 0) * 100}%` }}
        />
      </div>
    </div>
  )
}

export function ConversionPanel({ data }: { data: Conversion }) {
  return (
    <section className="mt-12">
      <SectionHeading hint="how often the game actually went that way">
        Converting the 15-minute state
      </SectionHeading>

      <div className="grid gap-8 sm:grid-cols-2">
        {data.splits.map(split => (
          <div key={split.label}>
            <p className="mb-4 text-[13px] text-neutral-300">{split.label}</p>
            <div className="flex gap-6">
              <Side text={split.ahead.text} games={split.ahead.games} rate={split.ahead.win_rate} tone="up" />
              <Side text={split.behind.text} games={split.behind.games} rate={split.behind.win_rate} tone="down" />
            </div>
          </div>
        ))}
      </div>

      <p className="mt-6 max-w-prose text-[12.5px] leading-relaxed text-neutral-600">{data.note}</p>
    </section>
  )
}
