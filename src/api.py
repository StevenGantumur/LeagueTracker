import os
import statistics
from contextlib import asynccontextmanager, contextmanager

import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# Games shorter than this are remakes -- an early surrender inside the first few
# minutes. They are excluded at collection time now, but the endpoint filters
# them too so any rows predating that fix stay out of the response.
REMAKE_DURATION_SECONDS = 300

# Below this many games on each side, a difference of means says almost nothing:
# one game can swing the average, and the standard deviation is unstable. Factors
# under this threshold are withheld rather than shown with a meaningless number
# attached -- most relevant when filtering to a rarely-played champion.
MIN_GAMES_PER_SIDE = 5


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One pool for the process rather than a fresh TCP connection and auth
    # handshake per request.
    app.state.pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1, maxconn=10, dsn=os.getenv("DATABASE_URL")
    )
    yield
    app.state.pool.closeall()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def get_cursor():
    """Lease a connection from the pool and always return it.

    The previous version called conn.close() after the query, so a failing query
    raised straight past it and leaked the connection.
    """
    conn = app.state.pool.getconn()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        app.state.pool.putconn(conn)


@app.get("/health")
def health():
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except psycopg2.Error:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ok"}


@app.get("/player")
def player():
    """Who is being tracked, and their overall record."""
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT game_name, tag_line, updated_at FROM players WHERE puuid = %s",
                (os.getenv("PUUID"),),
            )
            row = cur.fetchone()
            cur.execute(
                """SELECT count(*), count(*) FILTER (WHERE p.win)
                   FROM participants p JOIN matches m ON m.match_id = p.match_id
                   WHERE p.puuid = %s AND m.game_duration >= %s""",
                (os.getenv("PUUID"), REMAKE_DURATION_SECONDS),
            )
            games, wins = cur.fetchone()
    except psycopg2.Error:
        raise HTTPException(status_code=503, detail="database unavailable")

    if row is None:
        # Collection has run but the Riot ID lookup failed or has never run.
        return {"riot_id": None, "games": games, "wins": wins, "losses": games - wins}

    game_name, tag_line, updated_at = row
    return {
        "riot_id": f"{game_name}#{tag_line}",
        "game_name": game_name,
        "tag_line": tag_line,
        "name_checked_at": updated_at.isoformat(),
        "games": games,
        "wins": wins,
        "losses": games - wins,
        "win_rate": round(wins / games, 4) if games else None,
    }


@app.get("/stats/champions")
def champions(limit: int = 50):
    """Per-champion record and averages, most-played first."""
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                SELECT p.champion_id,
                       count(*)                        AS games,
                       count(*) FILTER (WHERE p.win)   AS wins,
                       avg(p.kills)                    AS kills,
                       avg(p.deaths)                   AS deaths,
                       avg(p.assists)                  AS assists,
                       avg(p.total_minions_killed)     AS cs,
                       avg(p.vision_score)             AS vision,
                       avg(m.game_duration)            AS duration
                FROM participants p
                JOIN matches m ON m.match_id = p.match_id
                WHERE p.puuid = %s AND m.game_duration >= %s
                GROUP BY p.champion_id
                ORDER BY games DESC, wins DESC
                LIMIT %s
                """,
                (os.getenv("PUUID"), REMAKE_DURATION_SECONDS, limit),
            )
            rows = cur.fetchall()
    except psycopg2.Error:
        raise HTTPException(status_code=503, detail="database unavailable")

    out = []
    for champ, games, wins, k, d_, a, cs, vision, duration in rows:
        out.append({
            "champion_id": champ,
            "games": games,
            "wins": wins,
            "losses": games - wins,
            "win_rate": round(wins / games, 4) if games else None,
            "kills": round(float(k), 1),
            "deaths": round(float(d_), 1),
            "assists": round(float(a), 1),
            # Deaths of zero would divide by zero; KDA is conventionally reported
            # as "perfect" there, so fall back to (K+A) rather than infinity.
            "kda": round((float(k) + float(a)) / float(d_), 2) if float(d_) else round(float(k) + float(a), 2),
            "cs": round(float(cs), 1),
            "vision_score": round(float(vision), 1),
            "avg_duration_min": round(float(duration) / 60, 1),
        })
    return {"champions": out}


@app.get("/stats/conversion")
def conversion():
    """How often a lead at 15 becomes a win, and how often a deficit is overturned.

    Effect sizes say how far apart wins and losses look. This says something more
    directly useful: given the state at minute 15, how often does the game
    actually go your way? It is the same data read as a conditional win rate.
    """
    params = {
        "minutes": [15],
        "puuid": os.getenv("PUUID"),
        "min_duration": REMAKE_DURATION_SECONDS,
        "champion_id": None,
    }
    try:
        with get_cursor() as cur:
            cur.execute(TEAM_QUERY, params)
            team = {r[0]: (r[1], float(r[3])) for r in cur.fetchall()}
            cur.execute(PERSONAL_QUERY, params)
            lane = {r[0]: (r[1], float(r[3])) for r in cur.fetchall()}
    except psycopg2.Error:
        raise HTTPException(status_code=503, detail="database unavailable")

    def split(source, label, ahead_text, behind_text):
        ahead = [win for win, value in source.values() if value > 0]
        behind = [win for win, value in source.values() if value <= 0]
        return {
            "label": label,
            "ahead": {
                "text": ahead_text,
                "games": len(ahead),
                "wins": sum(ahead),
                "win_rate": round(sum(ahead) / len(ahead), 4) if ahead else None,
            },
            "behind": {
                "text": behind_text,
                "games": len(behind),
                "wins": sum(behind),
                "win_rate": round(sum(behind) / len(behind), 4) if behind else None,
            },
        }

    return {
        "splits": [
            split(team, "Team gold at 15 min",
                  "Ahead as a team", "Behind as a team"),
            split(lane, "Your lane gold at 15 min",
                  "Winning your lane", "Losing your lane"),
        ],
        "note": (
            "Read as: given this state at minute 15, how often the game was won. "
            "Splitting at exactly zero puts near-even games on the 'behind' side, "
            "so the behind figure includes coinflips as well as real deficits."
        ),
    }


@app.get("/matches")
def matches(limit: int = 20, champion_id: int | None = None):
    columns = [
        "match_id", "champion_id", "kills", "deaths", "assists",
        "total_minions_killed", "gold_earned", "win",
    ]
    try:
        with get_cursor() as cur:
            # Joining matches serves two purposes: it exposes game_creation for a
            # real chronological sort (ordering by the match_id string only
            # happens to match chronology today), and game_duration for the
            # remake filter.
            cur.execute(
                """
                SELECT p.match_id, p.champion_id, p.kills, p.deaths, p.assists,
                       p.total_minions_killed, p.gold_earned, p.win
                FROM participants p
                JOIN matches m ON m.match_id = p.match_id
                WHERE p.puuid = %(puuid)s
                  AND m.game_duration >= %(min_duration)s
                  AND (%(champion_id)s IS NULL OR p.champion_id = %(champion_id)s)
                ORDER BY m.game_creation DESC
                LIMIT %(limit)s
                """,
                {
                    "puuid": os.getenv("PUUID"),
                    "min_duration": REMAKE_DURATION_SECONDS,
                    "champion_id": champion_id,
                    "limit": limit,
                },
            )
            rows = cur.fetchall()
    except psycopg2.Error:
        raise HTTPException(status_code=503, detail="database unavailable")

    return [dict(zip(columns, row)) for row in rows]


# --- win factors ---------------------------------------------------------
#
# Everything reported here is measured strictly before minute 15, so these are
# leading indicators rather than consequences of having already won. End-of-game
# stats (final gold, kills, damage) are deliberately excluded: a won game
# produces more of all of them, so ranking them as "win factors" would be
# reverse causation dressed up as insight.

# One row per player per minute. A game ending mid-minute emits a second partial
# frame inside that minute, so DISTINCT ON ordered by timestamp_ms keeps the
# regular 60s frame. Note frames are NOT on exact 60000ms boundaries -- Riot's
# timestamps drift (60000, 60001, ...) -- so selection must go through `minute`.
FRAMES_CTE = """
    WITH frames AS (
        SELECT DISTINCT ON (match_id, puuid, minute)
               match_id, puuid, minute, total_gold, minions, jungle_cs, level, xp
        FROM participant_timelines
        WHERE minute = ANY(%(minutes)s)
        ORDER BY match_id, puuid, minute, timestamp_ms
    )
"""

# Your own lane, against the opposing player in the same position.
PERSONAL_QUERY = FRAMES_CTE + """
    SELECT me.match_id, me_p.win, me.minute,
           me.total_gold - opp.total_gold                              AS gold_diff,
           (me.minions + me.jungle_cs) - (opp.minions + opp.jungle_cs) AS cs_diff,
           me.xp    - opp.xp                                           AS xp_diff,
           me.level - opp.level                                        AS level_diff
    FROM frames me
    JOIN participants me_p  ON me_p.match_id = me.match_id AND me_p.puuid = me.puuid
    JOIN matches m          ON m.match_id = me.match_id
    JOIN participants opp_p ON opp_p.match_id = me_p.match_id
                           AND opp_p.team_position = me_p.team_position
                           AND opp_p.team_id <> me_p.team_id
    JOIN frames opp ON opp.match_id = opp_p.match_id AND opp.puuid = opp_p.puuid
                   AND opp.minute = me.minute
    WHERE me.puuid = %(puuid)s AND m.game_duration >= %(min_duration)s
      AND (%(champion_id)s IS NULL OR me_p.champion_id = %(champion_id)s)
"""

# All five players summed, so it captures the state of the whole map rather
# than one matchup.
TEAM_QUERY = FRAMES_CTE + """
    , team AS (
        SELECT f.match_id, p.team_id, f.minute,
               sum(f.total_gold) AS gold, sum(f.xp) AS xp
        FROM frames f
        JOIN participants p ON p.match_id = f.match_id AND p.puuid = f.puuid
        GROUP BY 1, 2, 3
    )
    SELECT me.match_id, me.win, mine.minute,
           mine.gold - theirs.gold AS team_gold_diff,
           mine.xp   - theirs.xp   AS team_xp_diff
    FROM participants me
    JOIN matches m ON m.match_id = me.match_id
    JOIN team mine   ON mine.match_id = me.match_id AND mine.team_id = me.team_id
    JOIN team theirs ON theirs.match_id = me.match_id AND theirs.team_id <> me.team_id
                    AND theirs.minute = mine.minute
    WHERE me.puuid = %(puuid)s AND m.game_duration >= %(min_duration)s
      AND (%(champion_id)s IS NULL OR me.champion_id = %(champion_id)s)
"""

# Each role's own matchup, to show which lane's early state tracks your results.
ROLE_QUERY = FRAMES_CTE + """
    SELECT me.match_id, me.win, ally_f.minute, ally.team_position,
           ally_f.total_gold - enemy_f.total_gold AS role_gold_diff
    FROM participants me
    JOIN matches m ON m.match_id = me.match_id
    JOIN participants ally  ON ally.match_id = me.match_id AND ally.team_id = me.team_id
    JOIN participants enemy ON enemy.match_id = me.match_id AND enemy.team_id <> me.team_id
                           AND enemy.team_position = ally.team_position
    JOIN frames ally_f  ON ally_f.match_id = ally.match_id AND ally_f.puuid = ally.puuid
    JOIN frames enemy_f ON enemy_f.match_id = enemy.match_id AND enemy_f.puuid = enemy.puuid
                       AND enemy_f.minute = ally_f.minute
    WHERE me.puuid = %(puuid)s AND m.game_duration >= %(min_duration)s
      AND ally.team_position <> ''
      AND (%(champion_id)s IS NULL OR me.champion_id = %(champion_id)s)
"""

# Label, unit, group, and a concrete thing to do about it. Tips describe what
# tends to accompany wins in this player's own games -- correlation, not a
# guarantee -- so they are phrased as levers to try, not rules.
FACTOR_META = {
    "team_gold_diff": (
        "Team gold lead", "gold", "team",
        "By far the strongest signal in your games -- roughly double any single "
        "lane. Wins track the state of the whole map, not your matchup. The "
        "practical lever: once you hit 6 or shove the wave, spend that tempo "
        "somewhere else -- a roam, a dragon, a plate on another lane -- instead "
        "of farming a lane you have already won.",
    ),
    "team_xp_diff": (
        "Team XP lead", "XP", "team",
        "Moves almost in lockstep with team gold. Team-wide XP leads come from "
        "your side taking objectives and winning skirmishes together, so treat "
        "this as the same lever: group and contest earlier rather than farming "
        "side lanes to minute 20.",
    ),
    "gold_diff": (
        "Your gold lead over lane opponent", "gold", "personal",
        "A lane lead only counts once you convert it. If you are up gold and "
        "the wave is pushing, that is your cue to roam or take a plate "
        "elsewhere rather than sit in lane extending it.",
    ),
    "cs_diff": (
        "Your CS lead over lane opponent", "CS", "personal",
        "Your strongest personal metric. CS in the 10-15 window is the cheapest "
        "gold on the map -- no cooldowns, no risk. Before you leave for a roam, "
        "hit the wave first so the roam is free rather than paid for in minions.",
    ),
    "xp_diff": (
        "Your XP lead over lane opponent", "XP", "personal",
        "XP leads decide skirmishes more sharply than gold does -- a level "
        "advantage is stats plus an extra ability point. Avoid hovering near a "
        "fight you are not committing to; you lose the XP either way.",
    ),
    "level_diff": (
        "Your level lead over lane opponent", "levels", "personal",
        "Hitting 6 before your opponent is a roam window, not just a stat line. "
        "That gap is usually where a mid laner can make something happen on "
        "another lane before the enemy has their ultimate to answer it.",
    ),
    "role_TOP": (
        "Top lane gold lead", "gold", "role",
        "Mostly outside your control early. The realistic lever is objective "
        "timing -- making sure herald or a dragon gets used rather than letting "
        "top play a solo game.",
    ),
    "role_JUNGLE": (
        "Jungle gold lead", "gold", "role",
        "Reflects contested camps and early objectives. Showing for scuttle and "
        "the first dragon is the cheapest way for a mid laner to move this "
        "number, and it is far more reachable than top lane.",
    ),
    "role_MIDDLE": (
        "Mid lane gold lead", "gold", "role",
        "Whoever played mid on your team -- usually but not always you, so this "
        "tracks close to your own lane numbers without being identical. Ranks "
        "near the bottom of the five, though the gaps between lanes are inside "
        "the error band at this sample size. Read it as 'winning lane alone does "
        "not win the game', not as 'your lane does not matter'.",
    ),
    "role_BOTTOM": (
        "Bot lane gold lead", "gold", "role",
        "Tracks your wins more closely than your own lane does. A mid-to-bot "
        "roam or a dragon setup around minutes 8-12 puts your lead where it "
        "appears to matter most, and sets up the objective at the same time.",
    ),
    "role_UTILITY": (
        "Support gold lead", "gold", "role",
        "Largely a proxy for roams and plates rather than farm. A support who is "
        "ahead has usually been making plays -- pairing with those roams instead "
        "of staying in lane compounds them.",
    ),
}

GROUP_LABELS = {
    "team": "Whole team",
    "personal": "Your lane",
    "role": "Lane by lane",
}


def _cohens_d(wins, losses):
    """Standardised difference between the two groups.

    Raw deltas are not comparable across metrics -- 750 gold means nothing next
    to 14 CS. Dividing by the pooled standard deviation puts every metric on one
    scale so they can be ranked. Roughly: 0.2 small, 0.5 medium, 0.8 large.
    """
    if len(wins) < 2 or len(losses) < 2:
        return None
    sw, sl = statistics.stdev(wins), statistics.stdev(losses)
    n_w, n_l = len(wins), len(losses)
    pooled_var = ((n_w - 1) * sw**2 + (n_l - 1) * sl**2) / (n_w + n_l - 2)
    if pooled_var <= 0:
        return None
    return (statistics.mean(wins) - statistics.mean(losses)) / pooled_var**0.5


def _standard_error(n_w, n_l):
    """Approximate standard error of Cohen's d, for an honest uncertainty band.

    Without it the ranking looks more precise than it is: at ~190 games the
    error is around +/-0.15, which is wider than the gap between several lanes.
    """
    if n_w < 2 or n_l < 2:
        return None
    return ((n_w + n_l) / (n_w * n_l)) ** 0.5


@app.get("/stats/win-factors")
def win_factors(minutes: str = "10,15", champion_id: int | None = None):
    """Early-game metrics ranked by how strongly they separate wins from losses."""
    try:
        wanted = sorted({int(m) for m in minutes.split(",") if m.strip()})
    except ValueError:
        raise HTTPException(status_code=400, detail="minutes must be comma-separated integers")
    if not wanted:
        raise HTTPException(status_code=400, detail="at least one minute required")

    params = {
        "minutes": wanted,
        "puuid": os.getenv("PUUID"),
        "min_duration": REMAKE_DURATION_SECONDS,
        "champion_id": champion_id,
    }
    try:
        with get_cursor() as cur:
            cur.execute(PERSONAL_QUERY, params)
            personal = cur.fetchall()
            cur.execute(TEAM_QUERY, params)
            team = cur.fetchall()
            cur.execute(ROLE_QUERY, params)
            roles = cur.fetchall()
            # "Your lane" follows whatever role was actually played that game,
            # which is not always the same one -- surface the mix so the lane-by
            # -lane numbers are not mistaken for the personal ones.
            cur.execute(
                """SELECT p.team_position, count(*)
                   FROM participants p JOIN matches m ON m.match_id = p.match_id
                   WHERE p.puuid = %(puuid)s AND m.game_duration >= %(min_duration)s
                     AND (%(champion_id)s IS NULL OR p.champion_id = %(champion_id)s)
                   GROUP BY 1 ORDER BY 2 DESC""",
                params,
            )
            role_mix = cur.fetchall()
    except psycopg2.Error:
        raise HTTPException(status_code=503, detail="database unavailable")

    buckets = {}
    matches, wins_seen = set(), set()

    def collect(key, minute, win, value):
        slot = buckets.setdefault((key, minute), {True: [], False: []})
        slot[win].append(float(value))

    for match_id, win, minute, gold, cs, xp, level in personal:
        matches.add(match_id)
        if win:
            wins_seen.add(match_id)
        for key, value in (("gold_diff", gold), ("cs_diff", cs),
                           ("xp_diff", xp), ("level_diff", level)):
            collect(key, minute, win, value)

    for _match_id, win, minute, team_gold, team_xp in team:
        collect("team_gold_diff", minute, win, team_gold)
        collect("team_xp_diff", minute, win, team_xp)

    for _match_id, win, minute, position, role_gold in roles:
        collect("role_" + position, minute, win, role_gold)

    factors = []
    for (key, minute), groups in buckets.items():
        wins, losses = groups[True], groups[False]
        if key not in FACTOR_META:
            continue
        if len(wins) < MIN_GAMES_PER_SIDE or len(losses) < MIN_GAMES_PER_SIDE:
            continue
        label, unit, group, tip = FACTOR_META[key]
        d = _cohens_d(wins, losses)
        se = _standard_error(len(wins), len(losses))
        factors.append({
            "metric": key + "_" + str(minute),
            "label": label + " at " + str(minute) + " min",
            "group": group,
            "group_label": GROUP_LABELS[group],
            "minute": minute,
            "unit": unit,
            "tip": tip,
            "win_avg": round(statistics.mean(wins), 1),
            "loss_avg": round(statistics.mean(losses), 1),
            "delta": round(statistics.mean(wins) - statistics.mean(losses), 1),
            "effect_size": round(d, 3) if d is not None else None,
            "effect_size_error": round(se, 3) if se is not None else None,
            "sample": {"wins": len(wins), "losses": len(losses)},
        })

    factors.sort(key=lambda f: abs(f["effect_size"] or 0), reverse=True)

    warning = None
    if not factors and matches:
        warning = (
            f"Only {len(matches)} games match this filter. At least "
            f"{MIN_GAMES_PER_SIDE} wins and {MIN_GAMES_PER_SIDE} losses are "
            "needed before a difference of means means anything, so nothing is "
            "reported rather than showing a number built on a handful of games."
        )

    return {
        "warning": warning,
        "sample": {
            "matches": len(matches),
            "wins": len(wins_seen),
            "losses": len(matches) - len(wins_seen),
            "minutes": wanted,
            "roles_played": [{"position": r, "games": n} for r, n in role_mix],
            "champion_id": champion_id,
        },
        "note": (
            "All metrics are measured before minute 15, so they are leading "
            "indicators rather than consequences of winning. Effect size is "
            "Cohen's d over one player's games; the error band is roughly "
            "+/-0.15 at this sample size, which is wider than the gap between "
            "several of these lanes. Treat the ranking as suggestive and the "
            "tips as levers to try, not established causes."
        ),
        "factors": factors,
    }
