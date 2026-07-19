# LeagueTracker — Fix List (from code review, 2026-07-01)

Ordered so each step protects the ones after it. Hints included, solutions not —
work the problem first; ask for a review when a step is done.

## 1. Safety net (do first, ~5 min)
- [ ] Add `.DS_Store` and `.ipynb_checkpoints/` to `.gitignore`
- [ ] `git init` + first commit (`.env` is already ignored — verify with `git status` before committing)
- [ ] `pip freeze > requirements.txt` from the venv
- [ ] Delete the empty `match.json` (or save a real match response there as a test fixture for step 7)

**Why first:** everything after this becomes reversible.

## 2. Collector fixes — `src/collect.py`
- [ ] **Skip remakes.** Games with `gameDuration < 300` are remakes; 8 are already in your DB
      (69–316s, all participants 0/0/0). They skew loss averages and clutter the match list.
- [ ] **Handle 429 properly.** Right now any HTTP error skips the match. A 429 response has a
      `Retry-After` header — sleep that long and retry the same match instead of skipping.
- [ ] **Bug: the `continue` in the except block skips the 2.5s sleep** — so right after a 429,
      the next request fires with zero delay. Trace the loop flow and you'll see it.
- [ ] **Catch DB errors.** Only `requests` exceptions are caught. A psycopg2 error kills the run
      AND leaves the connection in an aborted transaction. You need a `rollback()` path.
- [ ] **Final timeline frame is silently lost.** Frames arrive every 60,000ms plus one partial
      frame at game end. `timestamp // 60000` maps the final frame to the same minute as the last
      full frame, and `ON CONFLICT DO NOTHING` eats it. (Verified: longest games have exactly
      max_frame+1 rows stored.) Decide: round differently, or store the raw timestamp.
- [ ] Delete `findOpponent` — dead code, and `your_position` is unbound if the player isn't found.

**Why:** every downstream layer consumes this data. Fix the source before the consumers.

## 3. Clean existing data (DESTRUCTIVE — print before deleting)
- [ ] Delete the 8 remake matches + their participant and timeline rows.
      `SELECT` them first, check the count is exactly 8, then delete inside one transaction.
      Mind the FK order: children before parent.

## 4. Schema + API — `SQL/schema.sql`, `src/api.py`
- [ ] `CREATE INDEX ON participants(puuid)` — the /matches query filters by puuid, but the PK
      `(match_id, puuid)` can't serve it. *Why: a composite B-tree is sorted by its first column.*
- [ ] Fix the connection leak: if the query throws, `conn.close()` never runs. Context managers.
      (Better: one pool at startup instead of a connection per request.)
- [ ] `ORDER BY match_id DESC` is string ordering — it happens to match chronology today
      (verified: 0 mismatches), but join `matches` and order by `game_creation` instead.
- [ ] Filter remakes out of the endpoint too (defense in depth vs. step 2).

## 5. ML notebook — `notebooks/exploration.ipynb` (most learning value here)
- [ ] **State the baseline.** Majority class is ~53% — that's the number 64% has to beat.
- [ ] **Kill the single split.** 39 test rows → ±0.15 CI on accuracy; the result is noise.
      Use stratified 5-fold CV, report mean ± std of AUC.
- [ ] **`champion_id` is a label, not a number.** LightGBM will split on "champion_id > 150".
      `astype("category")` or drop it.
- [ ] **Temporal split for the honest number.** Data spans patches 16.3–16.11. Train on the
      oldest ~80%, test on the newest. Expect the score to drop — that drop IS the finding.
- [ ] Shrink the model (154 rows can't feed 100 trees × 15 leaves — hence the wall of
      "no further splits" warnings). Try n_estimators=50, num_leaves=7.
- [ ] Add a markdown note: 8 matches drop out of the pivot (no minute-15 frame) — that's the
      remakes; selection bias is fine here but should be stated.
- [ ] Remove the duplicate groupby cell.

## 6. Frontend — `frontend/app/` (done by Claude 2026-07-07, at Steven's request)
- [x] Loading + error states on the fetch (API down currently = silently blank page)
- [x] Move `http://localhost:8000` to `NEXT_PUBLIC_API_URL` (see `frontend/.env.local`)
- [x] `champion_id` is fetched but never rendered — show champion names (Data Dragon has a
      free id→name JSON) or drop it from the query
- [x] `layout.tsx` metadata still says "Create Next App"

## 7. Tests
- [ ] Unit tests for `matchToRow`, `participantsToRows`, `timelinesToRows` against a saved
      real match/timeline JSON fixture. Pure functions — no mocking needed.

---
**Verified clean, don't touch:** tsc + ESLint pass; all matches have exactly 10 participants;
only queue 420 present; no ML data leakage (all features are pre-15-min).
