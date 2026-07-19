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

CREATE TABLE participant_timelines (
    match_id      VARCHAR(255) NOT NULL REFERENCES matches(match_id),
    puuid         VARCHAR(255) NOT NULL,
    minute        INT          NOT NULL,
    total_gold    INT          NOT NULL,
    minions       INT          NOT NULL,
    jungle_cs     INT          NOT NULL,
    level         INT          NOT NULL,
    xp            INT          NOT NULL,
    PRIMARY KEY (match_id, puuid, minute)
  );