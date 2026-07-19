"use client"

import { useEffect, useState } from "react"

interface Match {
  match_id: string
  champion_id: number
  kills: number
  deaths: number
  assists: number
  total_minions_killed: number
  gold_earned: number
  win: boolean
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

// Data Dragon is Riot's free static-data CDN — champion.json maps numeric
// champion keys to display names, keyed by the current patch version.
async function fetchChampionNames(): Promise<Record<number, string>> {
  const versions: string[] = await fetch(
    "https://ddragon.leagueoflegends.com/api/versions.json"
  ).then(res => res.json())
  const champions = await fetch(
    `https://ddragon.leagueoflegends.com/cdn/${versions[0]}/data/en_US/champion.json`
  ).then(res => res.json())
  const names: Record<number, string> = {}
  for (const champ of Object.values(champions.data) as { key: string; name: string }[]) {
    names[Number(champ.key)] = champ.name
  }
  return names
}

export default function Home() {
  const [matches, setMatches] = useState<Match[]>([])
  const [championNames, setChampionNames] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API_BASE}/matches`)
      .then(res => {
        if (!res.ok) throw new Error(`API returned ${res.status}`)
        return res.json()
      })
      .then(data => setMatches(data))
      .catch(err => setError(err instanceof Error ? err.message : "Failed to load matches"))
      .finally(() => setLoading(false))

    // Champion names are cosmetic — if Data Dragon is unreachable we still
    // render matches, just with the raw champion id as a fallback.
    fetchChampionNames()
      .then(setChampionNames)
      .catch(() => {})
  }, [])

  return (
    <main className="p-8 bg-gray-900 min-h-screen text-white">
      <h1 className="text-3xl font-bold mb-6">League Tracker</h1>

      {loading && <p className="text-gray-400">Loading matches…</p>}

      {error && (
        <div className="p-4 bg-red-900/50 border border-red-700 rounded text-red-200">
          <p className="font-bold">Couldn&apos;t load matches</p>
          <p className="text-sm mt-1">{error} — is the API running at {API_BASE}?</p>
        </div>
      )}

      {!loading && !error && matches.length === 0 && (
        <p className="text-gray-400">No matches found.</p>
      )}

      {matches.map(match => (
        <div key={match.match_id} className="mb-2 p-4 bg-gray-800 rounded flex gap-6">
          <span className={match.win ? "text-green-400 font-bold w-12" : "text-red-400 font-bold w-12"}>
            {match.win ? "WIN" : "LOSS"}
          </span>
          <span className="w-28 font-medium">
            {championNames[match.champion_id] ?? `Champion ${match.champion_id}`}
          </span>
          <span>{match.kills}/{match.deaths}/{match.assists}</span>
          <span>{match.total_minions_killed} CS</span>
          <span>{match.gold_earned.toLocaleString()} gold</span>
        </div>
      ))}
    </main>
  )
}
