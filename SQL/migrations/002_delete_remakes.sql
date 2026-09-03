-- Migration 002 -- DESTRUCTIVE
--
-- Removes remakes (games that ended in an early surrender) that were collected
-- before the collector learned to skip them. Remakes are ~1-5 minutes long with
-- every participant at 0/0/0; they drag down the loss-side averages and pad the
-- match list with games that were never played.
--
-- Run the SELECT block first and confirm the count matches what you expect
-- before running the DELETE block. Children are deleted before the parent to
-- respect the foreign keys.

-- ---- inspect first ----
SELECT match_id, game_duration, game_creation
FROM matches
WHERE game_duration < 300
ORDER BY game_creation;

SELECT count(*) AS remake_count FROM matches WHERE game_duration < 300;

-- ---- then delete ----
BEGIN;

DELETE FROM participant_timelines
WHERE match_id IN (SELECT match_id FROM matches WHERE game_duration < 300);

DELETE FROM participants
WHERE match_id IN (SELECT match_id FROM matches WHERE game_duration < 300);

DELETE FROM matches WHERE game_duration < 300;

COMMIT;
