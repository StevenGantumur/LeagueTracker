-- Migration 001
--
-- 1. Index participants(puuid) so /matches stops seq-scanning.
-- 2. Re-key participant_timelines on the raw frame timestamp instead of the
--    derived minute, so the partial frame Riot emits at game end is no longer
--    collapsed into the last full minute and swallowed by ON CONFLICT DO NOTHING.
--
-- NOTE: rows already in the table only have `minute`, so their timestamp_ms is
-- backfilled as minute * 60000. That is exact for every full frame. The final
-- partial frames were never stored in the first place -- this migration stops
-- the loss going forward, it cannot recover the frames already dropped. Re-run
-- the collector against an empty table if you want those backfilled for real.

BEGIN;

CREATE INDEX IF NOT EXISTS participants_puuid_idx ON participants (puuid);

ALTER TABLE participant_timelines ADD COLUMN timestamp_ms BIGINT;
UPDATE participant_timelines SET timestamp_ms = minute::BIGINT * 60000;
ALTER TABLE participant_timelines ALTER COLUMN timestamp_ms SET NOT NULL;

ALTER TABLE participant_timelines DROP CONSTRAINT participant_timelines_pkey;

-- An existing plain column cannot be converted to GENERATED in place, and
-- `minute` is fully derivable from timestamp_ms, so drop and redefine it.
ALTER TABLE participant_timelines DROP COLUMN minute;
ALTER TABLE participant_timelines
    ADD COLUMN minute INT GENERATED ALWAYS AS (timestamp_ms / 60000) STORED;

ALTER TABLE participant_timelines ADD PRIMARY KEY (match_id, puuid, timestamp_ms);

CREATE INDEX IF NOT EXISTS participant_timelines_minute_idx
    ON participant_timelines (match_id, puuid, minute);

COMMIT;
