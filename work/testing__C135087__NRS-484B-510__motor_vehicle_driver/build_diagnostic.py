"""Create nine-frame textual software fixtures, never physical evidence."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def content(value):
    return json.dumps(value, sort_keys=True) + "\n"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    patterns = {"clear_before_entry": (7, False),
                "entrant_during_loading": (3, True),
                "entrant_after_exchange": (6, True)}
    for suffix, (approach_start, blocked) in patterns.items():
        case = ROOT.name + "__" + suffix
        source = json.loads(json.dumps(base))
        packet = {"case_id": case, "source_kind": "synthetic_fixture",
                  "diagnostic_fixture": True, "restricted_purpose": "reserved vehicle parking",
                  "rows": []}
        for index in range(9):
            packet["rows"].append({"frame": index, "time_s": index / 20,
                "subject_station_m": 16, "subject_speed_mps": 0,
                "entrant_station_m": 4 if index < approach_start else 11,
                "entrant_waiting": blocked and index >= approach_start,
                "entrant_access_blocked": blocked and index >= approach_start,
                "passenger_exchange_active": 2 <= index < 6,
                "passenger_boarding_state": "approaching" if index < 2 else
                                            "boarding" if index < 6 else "aboard",
                "entrant_parking_task_active": True})
        source["files"]["original-attempt/site-packet.json"] = content(packet)
        source["files"]["fixture-provenance.json"] = content({
            "diagnostic_fixture": True, "scope": "software compatibility only",
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False})
        capture = json.loads(source["files"]["capture/manifest.json"])
        capture["case_id"] = case
        capture["acquisition"] = "synthetic_diagnostic_fixture"
        capture["source_run"] = "fixture:restricted-zone-software-compatibility"
        source["files"]["capture/manifest.json"] = content(capture)
        for video, name in zip(source["videos"],
                               ("overview", "approach", "reference_corner", "driver_reference")):
            video["path"] = name + ".mkv"
        path = ROOT / ("diagnostic-" + suffix + ".json")
        path.write_text(content(source))
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("diagnostic fixture exceeds return size")
        recipe = {"format": "worker-fixture-recipe",
                  "generator": {"source": "work/" + ROOT.name + "/" + path.name,
                                "sha256": sha(path)},
                  "sources": [{"path": "diagnostic-input.json",
                               "source": "work/" + ROOT.name + "/" + path.name,
                               "sha256": sha(path)}]}
        (ROOT / ("diagnostic-" + suffix + "-recipe.json")).write_text(
            json.dumps(recipe, indent=2, sort_keys=True) + "\n")
        print(suffix, path.stat().st_size)


if __name__ == "__main__":
    main()
