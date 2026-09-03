"use client"

import { useEffect, useState } from "react"
import {
  API_BASE,
  fetchChampionNames,
  getChampions,
  getConversion,
  getMatches,
  getPlayer,
  getWinFactors,
  percent,
  type Champion,
  type Conversion,
  type Match,
  type Player,
  type WinFactors,
} from "./lib/api"
import { ChampionFilter, ChampionTable } from "./components/Champions"
import { ConversionPanel } from "./components/Conversion"
import { SectionHeading } from "./components/SectionHeading"
import { WinFactorsPanel } from "./components/WinFactors"

export default function Home() {
  const [player, setPlayer] = useState<Player | null>(null)
  const [champions, setChampions] = useState<Champion[]>([])
  const [conversion, setConversion] = useState<Conversion | null>(null)
  const [names, setNames] = useState<Record<number, string>>({})

  const [championId, setChampionId] = useState<number | null>(null)
  const [matches, setMatches] = useState<Match[]>([])
  const [factors, setFactors] = useState<WinFactors | null>(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Loaded once. Not affected by the champion filter.
  useEffect(() => {
    getPlayer()
      .then(setPlayer)
      .catch(err => setError(err instanceof Error ? err.message : "Failed to reach the API"))
      .finally(() => setLoading(false))

    getChampions().then(r => setChampions(r.champions)).catch(() => {})
    getConversion().then(setConversion).catch(() => {})
    fetchChampionNames().then(setNames).catch(() => {})
  }, [])

  // Refetched on filter change.
  useEffect(() => {
    getMatches(championId).then(setMatches).catch(() => setMatches([]))
    getWinFactors(championId).then(setFactors).catch(() => setFactors(null))
  }, [championId])

  const selectedName = championId === null ? null : (names[championId] ?? `#${championId}`)

  return (
    <main className="mx-auto w-full max-w-3xl px-6 pb-24 pt-24">
      <header className="text-center">
        <h1 className="title-fade select-none text-[52px] font-medium leading-[1.05] tracking-[-0.03em] sm:text-[76px]">
          LeaguesAhead
        </h1>

        <p className="mt-5 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-[12px] text-neutral-500">
          <span className="rounded-full border border-amber-400/25 bg-amber-400/[0.07] px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-amber-200/70">
            Prototype
          </span>
          <span>One player&apos;s ranked games — not a public service.</span>
        </p>

        {player && (
          <p className="mt-3 text-[14px] text-neutral-300">
            {player.riot_id ?? "Unknown player"}
            <span className="tabular ml-3 text-[13px] text-neutral-500">
              {player.games} ranked games · {player.wins}W {player.losses}L ·{" "}
              {percent(player.win_rate)}
            </span>
          </p>
        )}

        {champions.length > 0 && (
          <ChampionFilter
            champions={champions}
            names={names}
            selected={championId}
            onSelect={setChampionId}
            totalGames={player?.games ?? 0}
          />
        )}

        {selectedName && (
          <p className="mt-4 text-[12.5px] text-neutral-500">
            Showing {selectedName} only — the stats below are filtered.{" "}
            <button
              onClick={() => setChampionId(null)}
              className="cursor-pointer text-neutral-300 underline underline-offset-2 hover:text-white"
            >
              Clear
            </button>
          </p>
        )}
      </header>

      <div className="text-left">
      {loading && <p className="mt-14 text-[13px] text-neutral-500">Loading…</p>}

      {error && (
        <div className="mt-14 border-l-2 border-rose-500/40 pl-4">
          <p className="text-[14px] text-rose-200">Couldn&apos;t reach the API</p>
          <p className="mt-1 text-[13px] text-neutral-500">
            {error} — is it running at {API_BASE}?
          </p>
        </div>
      )}

      {conversion && championId === null && <ConversionPanel data={conversion} />}

      {factors && factors.factors.length > 0 && <WinFactorsPanel data={factors} />}

      {factors && factors.factors.length === 0 && factors.warning && (
        <p className="mt-12 max-w-prose border-l border-white/10 pl-4 text-[13px] leading-relaxed text-neutral-500">
          {factors.warning}
        </p>
      )}

      {champions.length > 0 && (
        <ChampionTable
          champions={champions}
          names={names}
          selected={championId}
          onSelect={setChampionId}
        />
      )}

      {!loading && !error && (
        <section className="mt-12">
          <SectionHeading>{selectedName ? `Recent ${selectedName} games` : "Recent games"}</SectionHeading>

          {matches.length === 0 && <p className="text-[13px] text-neutral-500">No matches found.</p>}

          {matches.map(match => (
            <div
              key={match.match_id}
              className="flex items-baseline gap-4 border-b border-white/[0.06] py-3 last:border-0"
            >
              <span
                className={`w-6 text-[11px] font-medium uppercase tracking-wider ${
                  match.win ? "text-emerald-300/80" : "text-rose-300/60"
                }`}
              >
                {match.win ? "W" : "L"}
              </span>
              <span className="flex-1 text-[14px] text-neutral-200">
                {names[match.champion_id] ?? `#${match.champion_id}`}
              </span>
              <span className="tabular w-24 text-right text-[13px] text-neutral-400">
                {match.kills}/{match.deaths}/{match.assists}
              </span>
              <span className="tabular w-16 text-right text-[13px] text-neutral-500">
                {match.total_minions_killed} cs
              </span>
              <span className="tabular w-20 text-right text-[13px] text-neutral-500">
                {(match.gold_earned / 1000).toFixed(1)}k
              </span>
            </div>
          ))}
        </section>
      )}

        <footer className="mt-16 border-t border-white/[0.06] pt-6">
          <p className="max-w-prose text-[12.5px] leading-relaxed text-neutral-600">
            <span className="text-neutral-400">LeaguesAhead is a prototype.</span>{" "}
            It tracks a single hard-coded account, runs on a personal Riot API key
            that expires every 24 hours, and collects matches by hand rather than
            on a schedule — so there is no sign-up, no search, and the data stops
            at whenever collection last ran. Every figure describes roughly 190
            games from one player: they are patterns in this account&apos;s
            history, not general truths about the game, and nothing here is
            endorsed by or affiliated with Riot Games.
          </p>
        </footer>
      </div>
    </main>
  )
}
