CREATE TABLE matches (
    match_id VARCHAR(255) PRIMARY KEY,
    game_creation BIGINT NOT NULL,
    game_duration INT NOT NULL,
    game_version VARCHAR(255) NOT NULL,
    queue_id INT NOT NULL,
    winning_team_id INT NOT NULL
);

CREATE TABLE participants (
    match_id VARCHAR(255) NOT NULL REFERENCES matches(match_id),
    puuid VARCHAR(255) NOT NULL,
    team_id INT NOT NULL,
    team_position VARCHAR(255) NOT NULL,
    champion_id INT NOT NULL,
    kills INT NOT NULL,
    deaths INT NOT NULL,
    assists INT NOT NULL,
    gold_earned INT NOT NULL,
    total_minions_killed INT NOT NULL,
    neutral_minions_killed INT NOT NULL,
    total_damage_dealt_to_champions INT NOT NULL,
    vision_score INT NOT NULL,
    wards_placed INT NOT NULL,
    wards_killed INT NOT NULL,
    turret_takedowns INT NOT NULL,
    win BOOLEAN NOT NULL,
    PRIMARY KEY (match_id, puuid)
);

-- The PK (match_id, puuid) is a composite B-tree sorted by match_id first, so it
-- cannot serve a lookup that filters on puuid alone -- which is exactly what
-- /matches does. This index covers that access path.
CREATE INDEX participants_puuid_idx ON participants (puuid);

CREATE TABLE participant_timelines (
    match_id      VARCHAR(255) NOT NULL REFERENCES matches(match_id),
    puuid         VARCHAR(255) NOT NULL,
    -- Riot emits a frame every 60,000ms plus one partial frame at game end.
    -- Keying on minute alone collapsed that final frame into the last full
    -- minute, where ON CONFLICT DO NOTHING silently discarded it. Keying on the
    -- raw timestamp keeps every frame; minute stays derived for querying.
    timestamp_ms  BIGINT       NOT NULL,
    minute        INT          GENERATED ALWAYS AS (timestamp_ms / 60000) STORED,
    total_gold    INT          NOT NULL,
    minions       INT          NOT NULL,
    jungle_cs     INT          NOT NULL,
    level         INT          NOT NULL,
    xp            INT          NOT NULL,
    PRIMARY KEY (match_id, puuid, timestamp_ms)
);

-- Analysis queries filter by minute ("state at minute 15"), which the PK's
-- timestamp_ms cannot answer without a scan.
CREATE INDEX participant_timelines_minute_idx
    ON participant_timelines (match_id, puuid, minute);

-- Riot IDs are mutable and are not present in match data, so they are resolved
-- from account-v1 and cached here. The PUUID is the stable key -- never key
-- anything on the displayed name, which changes when a player renames.
CREATE TABLE players (
    puuid       VARCHAR(255) PRIMARY KEY,
    game_name   VARCHAR(255) NOT NULL,
    tag_line    VARCHAR(255) NOT NULL,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX players_riot_id_idx ON players (lower(game_name), lower(tag_line));

-- Champion filtering and per-champion aggregates both scan participants by
-- (puuid, champion_id); the puuid-only index cannot narrow the champion.
CREATE INDEX participants_puuid_champion_idx ON participants (puuid, champion_id);
