export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

export interface Match {
  match_id: string
  champion_id: number
  kills: number
  deaths: number
  assists: number
  total_minions_killed: number
  gold_earned: number
  win: boolean
}

export interface Player {
  riot_id: string | null
  games: number
  wins: number
  losses: number
  win_rate: number | null
}

export interface Champion {
  champion_id: number
  games: number
  wins: number
  losses: number
  win_rate: number | null
  kills: number
  deaths: number
  assists: number
  kda: number
  cs: number
  vision_score: number
  avg_duration_min: number
}

export interface WinFactor {
  metric: string
  label: string
  group: string
  group_label: string
  minute: number
  unit: string
  tip: string
  win_avg: number
  loss_avg: number
  delta: number
  effect_size: number | null
  effect_size_error: number | null
  sample: { wins: number; losses: number }
}

export interface WinFactors {
  warning: string | null
  sample: {
    matches: number
    wins: number
    losses: number
    minutes: number[]
    roles_played: { position: string; games: number }[]
    champion_id: number | null
  }
  note: string
  factors: WinFactor[]
}

export interface ConversionSide {
  text: string
  games: number
  wins: number
  win_rate: number | null
}

export interface Conversion {
  splits: { label: string; ahead: ConversionSide; behind: ConversionSide }[]
  note: string
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`API returned ${res.status}`)
  return res.json() as Promise<T>
}

export const getPlayer = () => get<Player>("/player")
export const getChampions = () => get<{ champions: Champion[] }>("/stats/champions")
export const getConversion = () => get<Conversion>("/stats/conversion")

const championParam = (id: number | null) => (id === null ? "" : `champion_id=${id}`)

export const getMatches = (championId: number | null) =>
  get<Match[]>(`/matches?limit=20&${championParam(championId)}`)

export const getWinFactors = (championId: number | null) =>
  get<WinFactors>(`/stats/win-factors?${championParam(championId)}`)

// Data Dragon is Riot's static-data CDN. champion.json maps numeric keys to
// names, per patch version.
export async function fetchChampionNames(): Promise<Record<number, string>> {
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

export function signed(value: number, unit: string) {
  const magnitude =
    unit === "levels"
      ? Math.abs(value).toFixed(1)
      : Math.round(Math.abs(value)).toLocaleString()
  return `${value < 0 ? "−" : "+"}${magnitude}`
}

export const percent = (rate: number | null) =>
  rate === null ? "—" : `${(rate * 100).toFixed(1)}%`
