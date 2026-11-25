"""CPU physical preparation checks; original Native realization remains unknown."""
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from gap_request import request_row
from runner import CAMERAS, FRAMES, RATE, RELEASE, check


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(condition):
    assert condition in RELEASE
    assert check()["geometry"]["authored_topology_passed"]
    assert FRAMES == 600 and RATE == 20 and len(CAMERAS) == 4
    rows = [request_row(i, "waited_entry" if condition == "condition_a" else
                        "early_entry") for i in range(FRAMES)]
    steps = [math.dist((a["ego"]["x_m"], a["ego"]["y_m"]),
                       (b["ego"]["x_m"], b["ego"]["y_m"]))
             for a, b in zip(rows, rows[1:])]
    if max(steps) > .4:
        raise ValueError("Authored ego request jumps between frames")
    base = json.loads((HERE / "native" / (condition + "-construction.json")).read_text())
    alt = json.loads((HERE / "fallbacks" / condition / "fallback1/construction.json").read_text())
    def config(value):
        return json.loads(next(item["content"] for item in value["files"]
                               if item["path"] == "config.json"))
    primary, fallback = config(base), config(alt)
    changed = {key for key in primary if primary[key] != fallback[key]}
    if changed != {"candidate_id", "steer_gain", "max_steer"}:
        raise ValueError("Fallback changed shared comparison contract")
    if primary["entry_release_s"] != RELEASE[condition]:
        raise ValueError("Selected entry release differs")
    return {"format": "c239014-physical-preparation-v1", "case_id": primary["case_id"],
            "primary_construction_sha256": sha(HERE / "native" / (condition + "-construction.json")),
            "fallback_construction_sha256": sha(HERE / "fallbacks" / condition / "fallback1/construction.json"),
            "camera_names": [camera[0] for camera in CAMERAS],
            "frames": FRAMES, "maximum_authored_ego_step_m": max(steps),
            "fallback_changed_knobs": sorted(changed),
            "original_native_executed": False, "physical_completion_claimed": False,
            "pending_original_checks": ["connected roundabout boundary", "ring-lane occupancy",
                                        "controller motion", "four actual camera streams"]}


if __name__ == "__main__":
    for condition in ("condition_a", "condition_b"):
        report = prove(condition)
        path = HERE / "proofs" / "physical" / condition / "proof.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"condition": condition, "sha256": sha(path)}, sort_keys=True))
