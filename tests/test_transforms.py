"""Tests for the pure row-building functions in src/collect.py.

These take a Riot API response and return tuples ready for psycopg2 -- no
network, no database, no mocking required.

The fixtures in tests/fixtures/ mirror the match-v5 response shape. Regenerate
them from a real match with `python tests/capture_fixture.py <match_id>` once a
Riot API key is available.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from collect import matchToRow, participantsToRows, timelinesToRows  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    with open(FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def match():
    return _load("match_sample.json")


@pytest.fixture
def timeline():
    return _load("timeline_sample.json")


# --- matchToRow ------------------------------------------------------------

def test_match_row_field_order_matches_insert(match):
    row = matchToRow(match)
    assert row == ("NA1_5000000001", 1751328000000, 1953, "16.11.700.4587", 420, 200)


def test_match_row_picks_the_winning_team(match):
    # Team 200 wins in the fixture; flipping it must flip the stored winner
    # rather than defaulting to whichever team is listed first.
    match["info"]["teams"] = [{"teamId": 100, "win": True}, {"teamId": 200, "win": False}]
    assert matchToRow(match)[5] == 100


# --- participantsToRows ----------------------------------------------------

def test_one_row_per_participant(match):
    rows = participantsToRows(match)
    assert len(rows) == 10
    assert len({(r[0], r[1]) for r in rows}) == 10, "rows must be unique on the PK"


def test_participant_row_carries_match_id_and_stats(match):
    rows = participantsToRows(match)
    first = rows[0]
    source = match["info"]["participants"][0]
    assert first[0] == "NA1_5000000001"
    assert first[1] == source["puuid"]
    assert (first[5], first[6], first[7]) == (source["kills"], source["deaths"], source["assists"])
    assert first[16] is source["win"]


def test_win_flag_follows_team(match):
    rows = participantsToRows(match)
    # teamId is index 2, win is index 16.
    assert all(row[16] == (row[2] == 200) for row in rows)


# --- timelinesToRows -------------------------------------------------------

def test_row_count_is_frames_times_participants(timeline):
    rows = timelinesToRows(timeline)
    assert len(rows) == len(timeline["info"]["frames"]) * 10


def test_final_partial_frame_survives(timeline):
    """Regression test for the frame that used to be silently dropped.

    The fixture ends at 32:33, so its last two frames are at 1_920_000ms and
    1_953_000ms. Both floor to minute 32; keying the table on minute meant the
    second one collided with the first and ON CONFLICT DO NOTHING discarded it.
    """
    rows = timelinesToRows(timeline)
    keys = {(match_id, puuid, ts) for match_id, puuid, ts, *_ in rows}
    assert len(keys) == len(rows), "primary key must be unique across all frames"

    timestamps = sorted({ts for _, _, ts, *_ in rows})
    assert timestamps[-2:] == [1_920_000, 1_953_000]
    assert timestamps[-1] // 60000 == timestamps[-2] // 60000 == 32, (
        "fixture must exercise the collision case: two frames in the same minute"
    )


def test_timestamps_are_raw_not_bucketed(timeline):
    """Timestamps must be passed through untouched.

    Deliberately not asserting that frames land on exact multiples of 60000 --
    real Riot data drifts by a few milliseconds (60000, 60001, 60002, ...), so
    that assumption would fail the moment these fixtures are replaced with a
    real captured match.
    """
    rows = timelinesToRows(timeline)
    source = {f["timestamp"] for f in timeline["info"]["frames"]}
    assert {ts for _, _, ts, *_ in rows} == source, "timestamps must be verbatim"
    assert max(ts for _, _, ts, *_ in rows) > 60_000, "minute indexes leaked in as timestamps"


def test_participant_ids_map_to_puuids(timeline):
    rows = timelinesToRows(timeline)
    expected = {p["puuid"] for p in timeline["info"]["participants"]}
    assert {puuid for _, puuid, *_ in rows} == expected


def test_timeline_stats_column_order(timeline):
    rows = timelinesToRows(timeline)
    frame = timeline["info"]["frames"][0]
    pframe = frame["participantFrames"]["1"]
    match_id, puuid, ts, total_gold, minions, jungle_cs, level, xp = rows[0]
    assert ts == frame["timestamp"]
    assert (total_gold, minions, jungle_cs, level, xp) == (
        pframe["totalGold"], pframe["minionsKilled"],
        pframe["jungleMinionsKilled"], pframe["level"], pframe["xp"],
    )
