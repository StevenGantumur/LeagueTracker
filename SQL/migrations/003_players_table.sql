-- Migration 003: cache Riot IDs, and index champion lookups.
--
-- Match data carries only PUUIDs, so the displayed Riot ID has to come from
-- account-v1 and be stored. Keyed on PUUID because names are mutable.

BEGIN;

CREATE TABLE IF NOT EXISTS players (
    puuid       VARCHAR(255) PRIMARY KEY,
    game_name   VARCHAR(255) NOT NULL,
    tag_line    VARCHAR(255) NOT NULL,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS players_riot_id_idx ON players (lower(game_name), lower(tag_line));
CREATE INDEX IF NOT EXISTS participants_puuid_champion_idx ON participants (puuid, champion_id);

COMMIT;
