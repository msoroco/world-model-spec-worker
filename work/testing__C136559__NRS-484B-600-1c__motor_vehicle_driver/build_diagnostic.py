"""Create explicit synthetic posted-speed sources for pinned compatibility."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from posted_site import CASES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / "runtime/fixtures/example.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def content(value: dict) -> str:
    return json.dumps(value, sort_keys=True) + "\n"


def main() -> None:
    base = json.loads(BASE.read_text())
    times = [json.loads(line)["time_s"] for line in base["files"]["trace.jsonl"].splitlines() if line]
    if len(times) != 9:
        raise ValueError("pinned diagnostic scaffold changed")
    for suffix in CASES:
        exact = ROOT.name + "__" + suffix
        source = json.loads(json.dumps(base))
        files = source["files"]
        speed = 10.0 if suffix == "below" else 11.176 if suffix == "equal" else 12.0
        samples = [{"time_s": time, "speed_mps": speed,
                    "diagnostic_governed": suffix not in ("outside_zone", "opposite_direction", "non_authority_sign")}
                   for time in times]
        packet = {"case_id": exact, "source_kind": "synthetic_fixture",
                  "diagnostic_fixture": True,
                  "synthetic_posted_rate": 40.2336 if suffix == "metric_equivalent" else 25,
                  "synthetic_unit": "km/h" if suffix == "metric_equivalent" else "mph",
                  "samples": samples,
                  "physical_acceptance_claimed": False,
                  "legal_applicability": "unresolved"}
        files["original-attempt/posted-speed-source.json"] = content(packet)
        files["fixture-provenance.json"] = content({"diagnostic_fixture": True,
            "scope": "synthetic posted-speed software compatibility",
            "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False, "frames": 9})
        capture = json.loads(files["capture/manifest.json"])
        capture["case_id"] = exact
        capture["acquisition"] = "synthetic_diagnostic_fixture"
        capture["source_run"] = "fixture:posted-speed-software-compatibility"
        files["capture/manifest.json"] = content(capture)
        path = ROOT / ("diagnostic-" + suffix + ".json")
        path.write_text(content(source))
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("diagnostic UTF-8 file too large")
        digest = sha(path.read_bytes())
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json",
                               "source": "work/" + ROOT.name + "/" + path.name,
                               "sha256": digest}],
                  "generator": {"source": "work/" + ROOT.name + "/" + path.name,
                                "sha256": digest}}
        (ROOT / ("diagnostic-" + suffix + "-recipe.json")).write_text(
            json.dumps(recipe, indent=2, sort_keys=True) + "\n")
        print(suffix, path.stat().st_size)


if __name__ == "__main__":
    main()
