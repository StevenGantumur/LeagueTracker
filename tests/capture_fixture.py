"""Replace the test fixtures with a real Riot API response.

The committed fixtures are hand-built to the match-v5 schema so the test suite
runs without a Riot key. Once you have a key, capture a real match instead --
the tests then run against Riot's actual field names and shapes:

    python tests/capture_fixture.py NA1_5000000001

Pick a match that ended mid-minute (any normal-length game) so the final partial
timeline frame is present -- that is the case test_final_partial_frame_survives
depends on.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from collect import getMatchDetails, getMatchTimeline  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def main():
    if len(sys.argv) != 2:
        sys.exit(f"usage: python {Path(__file__).name} <match_id>")
    match_id = sys.argv[1]

    for name, payload in [
        ("match_sample.json", getMatchDetails(match_id)),
        ("timeline_sample.json", getMatchTimeline(match_id)),
    ]:
        path = FIXTURES / name
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        print(f"wrote {path}")

    print(
        "\nFixtures replaced. The assertions in tests/test_transforms.py hardcode "
        "values from the old fixture (match id, durations, timestamps) -- update "
        "them to match this match before committing."
    )


if __name__ == "__main__":
    main()
