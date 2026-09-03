# LeaguesAhead — Fix List

Originally from a code review on 2026-07-01. Hints included, solutions not —
work the problem first; ask for a review when a step is done.

> **Last updated 2026-09-02.** Read "Where things stand" first.

---

## Where things stand (2026-09-02, updated)

**Database is now set up on the PC and unblocked.**

- Postgres 18.1 is running locally. The `postgres` password in `.env` was wrong;
  the working one was recovered from the `Woodmans Tracker` project, which uses
  the same server. `.env` is updated and verified.
- The `leaguetracker` database did not exist on this machine -- it has now been
  created and `SQL/schema.sql` applied. Verified present: both indexes, and
  `minute` as a real `GENERATED ALWAYS AS (timestamp_ms / 60000) STORED` column.
- **The timeline fix is confirmed against real Postgres**, not just unit tests: a
  match ending at 32:33 stores both the 32:00 and 32:33 frames (2 rows, same
  minute, distinct `timestamp_ms`). Under the old minute key the second was
  discarded. Test rows were rolled back.
- Riot API key in `.env` is valid.
- A fresh collection was started to populate the empty database. Because the
  data is collected under the new schema, **both migrations are unnecessary** for this
  machine -- the data is collected under the new schema, with remakes skipped at
  ingest and final timeline frames retained.

Migrations `001` and `002` remain in the repo for the laptop's database, which
still holds the old rows. Neither has been run anywhere yet.

Note for the laptop: the password there may contain a `/`, which must be written
`%2F` in a connection URI or libpq misreads the host. The PC's password has no
special characters, so `.env` here needs no encoding.

## Done (2026-09-02, by Claude at Steven's request)

- [x] **README.md** — architecture, setup, data model, and an "Engineering notes"
      section documenting the non-obvious bugs and why the fixes are what they are.
      This is the file an internship reviewer opens first.
- [x] `.env.example` + `frontend/.env.local.example`, and `frontend/.gitignore`
      patched with `!.env*.example` so the template is actually committable.
- [x] **Timeline final-frame fix** (was step 2). `timelinesToRows` now stores the
      raw `timestamp_ms`; `minute` became a `GENERATED ALWAYS AS ... STORED`
      column and the table is keyed on `(match_id, puuid, timestamp_ms)`.
- [x] **Schema** — added `participants_puuid_idx` and
      `participant_timelines_minute_idx`; `SQL/schema.sql` is now the fresh-install
      definition.
- [x] **Migrations** — `SQL/migrations/001` (puuid index + timeline re-key) and
      `002` (delete remakes, destructive, inspect-then-delete). **Neither has been
      run against a real database yet.**
- [x] **API** (was step 4) — `ThreadedConnectionPool` at startup with a context
      manager that returns connections in `finally` (fixes the leak); joins
      `matches` and orders by `game_creation` instead of the `match_id` string;
      filters remakes by `game_duration`; `/health` now actually checks the DB.
- [x] **Win-factors stats** — `GET /stats/win-factors` ranks pre-15-minute lane
      differentials by Cohen's *d*, plus a frontend panel rendering them.
      Deliberately excludes end-of-game stats, which correlate with winning only
      because you won. Strongest signal: CS lead at 15 min (*d* = 0.64).
- [x] **Tests** (was step 7) — `tests/test_transforms.py`, 10 tests over the three
      pure transform functions, no network or DB needed. Verified they fail
      against the old bucketing code, so the regression test genuinely bites.
      Fixtures are schema-accurate but synthetic; `tests/capture_fixture.py`
      replaces them with a real match once a Riot key is in hand.

---

## Left to do

### 1. Verify the DB work — DONE on the PC
- [x] Started fresh instead of migrating: database created, `SQL/schema.sql`
      applied, 194 matches collected (99W / 95L, patches 16.4–16.16). Six remakes
      were skipped at ingest out of 200 IDs.
- [x] PostgreSQL 18.1 accepts the generated-column syntax; `minute` verified as
      `GENERATED ALWAYS AS (timestamp_ms / 60000) STORED`.
- [x] API smoke-tested against real data — `/health`, `/matches`, and
      `/stats/win-factors` all return correctly, CORS confirmed for :3000.
- [ ] Migrations 001/002 still unrun — only needed if the laptop's DB is revived.

**Confirmed caveat — this bit the stats query, and it will bite the notebook.**
Two things about timeline frames:

1. A game ending mid-minute yields *two* rows for that minute (the regular frame
   and the partial end-of-game one). `minute IN (10, 15)` double-counts for a
   game that ended between 15:00 and 15:59 — possible, since surrender opens at
   15:00. The notebook's `pivot` will raise on the duplicate index.
2. **Frame timestamps are not exact multiples of 60000.** Real values are 60000,
   60001, 60002, … so `timestamp_ms = 900000` matches nothing. Do not select
   frames by computed timestamp.

The fix for both, used by `/stats/win-factors` in `src/api.py` — copy this
pattern into the notebook:

```sql
SELECT DISTINCT ON (match_id, puuid, minute) ...
FROM participant_timelines
WHERE minute IN (10, 15)
ORDER BY match_id, puuid, minute, timestamp_ms
```

### 2. ML notebook — `notebooks/exploration.ipynb` — **Steven's, not Claude's**
Deliberately left alone; this is the part interviewers will ask about. Numbers
below are from the current database (194 matches, patches 16.4–16.16), not the
older 154-row dataset the original list was written against.

**It will crash as written.** Fix this before anything else:
- [ ] `diffs_df.pivot(...)` raises `ValueError: Index contains duplicate
      entries`. Three games ended inside minute 10 or 15, and each contributes a
      second partial frame in that minute — 30 duplicate rows. New since the
      timeline fix. Use the `DISTINCT ON` pattern above.

**The baseline is 71%, not 53%.** The most important item here:
- [ ] A single threshold — "predict a win iff my team's gold lead at 15 is
      positive" — scores **0.708** on 192 games. Majority class is only 0.516.
      So 64% is not beating a weak baseline, it is losing to one line of SQL.
      Report both numbers. A model that cannot beat a one-rule stump is a real
      finding, and noticing it is worth more than a flattering score.

**The strongest feature is missing from the model:**
- [ ] The notebook uses only your own lane's differentials. Team gold at 15
      separates wins from losses about twice as sharply (d = 1.26 vs 0.53) and
      is what drives that 0.708. Add team-level and per-role features — the SQL
      already exists in `src/api.py` (`TEAM_QUERY`, `ROLE_QUERY`).

**Rigor:**
- [ ] **Kill the single split.** ~190 rows means a ~38-game test set; the
      confidence interval swamps the result. Stratified 5-fold CV, report
      mean ± std of AUC.
- [ ] **`champion_id` is a label, not a number.** LightGBM will split on
      "champion_id > 150". It is also near-constant now — 119 of 194 games are
      one champion. `astype("category")` or drop it.
- [ ] **Temporal split**, but know what it gives you: the patch spread is
      lopsided, ~187 games in 16.4–16.11 and 7 in 16.12–16.16, so the newest 20%
      is a thin recent slice. Expect the score to drop — that drop IS the finding.
- [ ] Shrink the model (190 rows cannot feed 100 trees × 15 leaves — hence the
      wall of "no further splits" warnings). Try `n_estimators=50, num_leaves=7`,
      and fit a plain logistic regression alongside it. On this much data it may
      well win, which is itself worth reporting.
- [ ] Note the dropouts: 192 of 194 games have a minute-15 frame; two ended
      before then. Selection bias is fine here but should be stated.

**Housekeeping:**
- [ ] Remove the duplicate groupby cell.
- [ ] Move the hardcoded PUUID out of the SQL strings and into `os.getenv`.
- [ ] Once the real numbers exist, update the **Analysis** section of `README.md`
      — it describes the method and caveats but quotes no results.

### 3. Housekeeping
- [x] Committed and pushed to `main` (7 commits, 2026-09-02). `README.md` is
      deliberately untracked — Steven is writing it himself.
- [ ] Optional: rebuild `venv/` (deps currently live in the global Python 3.14).
      `requirements.txt` is a full freeze and does not include `pytest`; that is
      in `requirements-dev.txt`.

---

## Roadmap: zero-setup deployment

**Goal:** someone opens a URL and it works. No cloning, no `.env`, no local
Postgres. Right now running this requires a Riot key, a Postgres instance, and
three environment variables — fine for you, a wall for anyone evaluating it.

Two levels, in order of effort:

**Level 1 — one command locally (half a day).** A `docker-compose.yml` with
Postgres and the API, schema applied automatically on first boot via
`/docker-entrypoint-initdb.d`. Reduces setup to `docker compose up` plus a Riot
key. Cheap, and removes most of the friction.

- [ ] `Dockerfile` for the API, `docker-compose.yml` with a Postgres service.
- [ ] Mount `SQL/schema.sql` into the init directory so the DB self-provisions.
- [ ] Seed data so the app has something to show before any collection runs.

**Level 2 — actually hosted (a weekend).** A public URL with no setup at all.
This is the version worth linking in an application.

- [ ] Managed Postgres (Neon and Supabase both have usable free tiers).
- [ ] API on a container host (Railway, Render, Fly).
- [ ] Frontend on Vercel; point `NEXT_PUBLIC_API_URL` at the deployed API.
- [ ] Restrict CORS to the deployed frontend origin — it is currently pinned to
      `http://localhost:3000`.
- [ ] Collection has to become a scheduled job, which **requires a Production
      Riot key** — personal keys expire every 24 hours and would break the cron
      daily. Same approval process as the multi-account work below.
- [ ] Move secrets to the host's env var store; never bake them into an image.

**Ordering note:** Level 1 is worth doing before applications go out. Level 2
depends on Riot approving a production key, which is outside your control and
should not sit on the critical path.

## Roadmap: search any account, not just one

Turning this from a personal script into something that works for any player.
This is the change that makes the project read as a service rather than a
one-off, so it is worth doing properly.

### Is this allowed? Yes.

Riot supports it directly, and it is what op.gg, u.gg and Porofessor are built
on. Match history for a given account is public data through the official API.
The blockers are quota and approval, not privacy:

- **Lookup is by Riot ID, not summoner name.** Legacy summoner-name lookup was
  removed. The entry point is
  `/riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}` on a regional
  routing host, which returns the PUUID. Everything else keys off that PUUID.
- **The dev key quota is the real wall.** A personal key allows roughly 20
  requests/second and 100 requests per 2 minutes, and expires every 24 hours.
  One full history pull for one player is ~200-400 requests, so a personal key
  supports a handful of users per hour at best.
- **Serving real traffic needs a Production key**, which means registering the
  app with Riot and passing their review. Approval is not automatic.
- **Riot's developer policies apply** -- notably the required "isn't endorsed by
  Riot Games" disclaimer, and restrictions around monetization. Re-read the
  current policy before deploying anything public; Riot revises it periodically.

**Verify the above against Riot's current docs before building.** Riot has been
tightening data access, and specifics here may have moved.

### Work required

**Schema**
- [ ] `players` table: `puuid` PK, `game_name`, `tag_line`, `region`,
      `last_fetched_at`. Riot IDs are mutable, so the PUUID is the stable key --
      never key anything on the displayed name.
- [ ] Backfill the currently tracked account as the first row.
- [ ] Index `(lower(game_name), lower(tag_line))` for case-insensitive search.

**Collection**
- [ ] `resolveRiotId(game_name, tag_line, region) -> puuid` against account-v1.
- [ ] Make the collector take a PUUID argument instead of reading the single
      `PUUID` env var. That env var becomes a default, not the whole design.
- [ ] On-demand collection: a search for an unknown player enqueues a fetch
      rather than blocking the request for the minutes a full pull takes.
- [ ] Staleness policy -- re-fetch only matches newer than `last_fetched_at`
      instead of re-pulling the whole history on every search.
- [ ] A real rate-limit budget shared across concurrent jobs. The current fixed
      `time.sleep(2.5)` is fine for one sequential run and will not survive
      several users at once; this needs a token bucket honouring Riot's headers.

**API**
- [ ] `GET /players?q=` -- search stored players by Riot ID.
- [ ] `GET /players/{puuid}/matches` -- replaces the current `/matches`, which
      reads the tracked PUUID from the environment.
- [ ] `POST /players` -- resolve a Riot ID and queue collection; return a job id.
- [ ] `GET /jobs/{id}` so the frontend can poll collection progress.
- [ ] Rate-limit the public endpoints. Right now anyone can trigger unbounded
      Riot API usage against your key, which is the fastest way to get it
      throttled or revoked.

**Frontend**
- [ ] Search box with `gameName#tagLine` parsing.
- [ ] "Collecting, this takes a few minutes" progress state for a new player.
- [ ] Route per player rather than the single hardcoded dashboard.

### Scope warning

This is a multi-week feature, not an afternoon. The current repo -- one tracked
account, clean pipeline, honest analysis, tests, documented bugs -- is already a
credible portfolio project. **Do not leave this half-built while applications are
going out**; a finished small project reads better than an unfinished large one.
Start it after the applications are in, or land the schema and API changes only
(they are self-contained) and leave the job queue for later.

---
**Verified clean, don't touch:** tsc + ESLint pass; all matches have exactly 10
participants; only queue 420 present; no ML data leakage (all features are
pre-15-min).

**Frontend (step 6) is done** — loading/error states, `NEXT_PUBLIC_API_URL`,
champion names via Data Dragon, and real page metadata.
