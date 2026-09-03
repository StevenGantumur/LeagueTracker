"use client"

import { percent, type Champion } from "../lib/api"
import { SectionHeading } from "./SectionHeading"

// Under this, a win rate is mostly noise. Greyed rather than hidden.
const CONFIDENT_SAMPLE = 10

export function ChampionFilter({
  champions,
  names,
  selected,
  onSelect,
  totalGames,
}: {
  champions: Champion[]
  names: Record<number, string>
  selected: number | null
  onSelect: (id: number | null) => void
  totalGames: number
}) {
  const shown = champions.filter(c => c.games >= 3).slice(0, 8)

  const chip = (active: boolean) =>
    `cursor-pointer rounded-full border px-3 py-1.5 text-[12.5px] transition-colors ${
      active
        ? "border-white/25 bg-white/10 text-white"
        : "border-white/10 text-neutral-400 hover:border-white/20 hover:text-neutral-200"
    }`

  return (
    <div className="mt-8 flex flex-wrap justify-center gap-2">
      <button onClick={() => onSelect(null)} className={chip(selected === null)}>
        All champions
        <span className="tabular ml-2 text-[11px] text-neutral-500">{totalGames}</span>
      </button>
      {shown.map(c => (
        <button
          key={c.champion_id}
          onClick={() => onSelect(c.champion_id)}
          className={chip(selected === c.champion_id)}
        >
          {names[c.champion_id] ?? `#${c.champion_id}`}
          <span className="tabular ml-2 text-[11px] text-neutral-500">{c.games}</span>
        </button>
      ))}
    </div>
  )
}

export function ChampionTable({
  champions,
  names,
  selected,
  onSelect,
}: {
  champions: Champion[]
  names: Record<number, string>
  selected: number | null
  onSelect: (id: number | null) => void
}) {
  return (
    <section className="mt-12">
      <SectionHeading hint="click to filter everything above">Champions</SectionHeading>

      <div className="flex items-baseline gap-3 pb-2 text-[11px] text-neutral-600">
        <span className="flex-1">champion</span>
        <span className="tabular w-12 text-right">games</span>
        <span className="tabular w-16 text-right">win rate</span>
        <span className="tabular w-14 text-right">kda</span>
        <span className="tabular w-14 text-right">cs</span>
        <span className="tabular w-16 text-right">length</span>
      </div>

      {champions.map(c => {
        const confident = c.games >= CONFIDENT_SAMPLE
        const active = selected === c.champion_id
        return (
          <button
            key={c.champion_id}
            onClick={() => onSelect(active ? null : c.champion_id)}
            className={`flex w-full cursor-pointer items-baseline gap-3 border-b border-white/[0.06] py-2.5 text-left transition-colors last:border-0 ${
              active ? "bg-white/[0.04]" : "hover:bg-white/[0.02]"
            }`}
          >
            <span className={`flex-1 text-[14px] ${active ? "text-white" : "text-neutral-200"}`}>
              {names[c.champion_id] ?? `#${c.champion_id}`}
            </span>
            <span className="tabular w-12 text-right text-[13px] text-neutral-500">{c.games}</span>
            <span
              className={`tabular w-16 text-right text-[13px] ${
                !confident
                  ? "text-neutral-600"
                  : (c.win_rate ?? 0) >= 0.5
                    ? "text-emerald-300/80"
                    : "text-rose-300/70"
              }`}
            >
              {percent(c.win_rate)}
            </span>
            <span className="tabular w-14 text-right text-[13px] text-neutral-500">{c.kda}</span>
            <span className="tabular w-14 text-right text-[13px] text-neutral-500">{c.cs}</span>
            <span className="tabular w-16 text-right text-[13px] text-neutral-600">
              {c.avg_duration_min}m
            </span>
          </button>
        )
      })}

      <p className="mt-4 max-w-prose text-[12.5px] leading-relaxed text-neutral-600">
        Win rates on fewer than {CONFIDENT_SAMPLE} games are greyed out — at that
        sample a single game moves the number by ten points or more, so they
        describe the games played rather than how well the champion goes.
      </p>
    </section>
  )
}
