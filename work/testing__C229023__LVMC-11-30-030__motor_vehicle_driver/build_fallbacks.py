"""Create source-gated, slower approach alternatives for exact crosswalk cases.

These are engineering plans. A reviewed original site and trace must establish
whether a fallback is needed or physically succeeds.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from case_construction import CASES
from crosswalk_measurements import ASSIGNMENT_ID

HERE = Path(__file__).resolve().parent
CAP_MPS = 3.0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(seal_offline: bool = False) -> dict:
    draft = json.loads((HERE / "execution-manifest.draft.json").read_text())
    if {row["case_id"] for row in draft["cases"]} != {ASSIGNMENT_ID + "__" + s for s in CASES}:
        raise ValueError("all six exact primary cases required")
    alternatives = {}
    for row in draft["cases"]:
        suffix = row["case_id"].removeprefix(ASSIGNMENT_ID + "__")
        primary_path = HERE / row["construction"]
        if sha(primary_path) != row["construction_sha256"]:
            raise ValueError("primary construction changed")
        construction = json.loads(primary_path.read_text())
        config = next(item for item in construction["files"] if item["path"] == "config.json")
        selected = json.loads(config["content"])
        if selected["selected_case_id"] != row["case_id"] or selected.get("engineering_speed_cap_mps") is not None:
            raise ValueError("primary already has a speed cap")
        selected["engineering_speed_cap_mps"] = CAP_MPS
        config["content"] = json.dumps(selected, indent=2) + "\n"
        alternative_path = HERE / ("construction-" + suffix + "-fallback1.json")
        alternative_path.write_text(json.dumps(construction, indent=2) + "\n")
        offline = {"status": "pending exact fallback offline check"}
        if seal_offline:
            log = HERE / ("cpu-fallback-offline-" + suffix + ".log")
            receipt = json.loads(log.read_text())
            if (receipt.get("case_id") != row["case_id"] or receipt.get("candidate_id") != "fallback1"
                    or receipt.get("offline_passed") is not True or receipt.get("simulation_started") is not False):
                raise ValueError("exact fallback offline proof failed")
            offline = {"command": ".venv-cpu/bin/python runtime.py offline --manifest work/"
                       + ASSIGNMENT_ID + "/execution-manifest.json --case " + row["case_id"]
                       + " --candidate fallback1 --output .runtime-work/lead-nov24-fallback/fallback-" + suffix
                       + " --python $PWD/.venv-cpu/bin/python",
                       "exit_code": 0, "construction_sha256": sha(alternative_path),
                       "log": log.name, "log_sha256": sha(log)}
        alternatives[row["case_id"]] = {
            "id": "fallback1", "construction": alternative_path.name,
            "construction_sha256": sha(alternative_path),
            "trigger": {
                "source": "sealed original Native ego/pedestrian actor trace and four-view frame map",
                "metric": "ego crossing entry time minus pedestrian clearance time, seconds",
                "failure_condition": "ego enters the crossing before the original pedestrian has cleared; select a slower approach for a new original attempt",
            },
            "changed_knobs": [{"name": "engineering_speed_cap_mps", "primary": "reviewed original actor target up to 15 m/s", "fallback": CAP_MPS}],
            "offline": offline,
            "compatibility": {"status": "pending source-shaped positive and missing-source negative"},
        }
    output = {"format": "worker-fallback-draft", "assignment_id": ASSIGNMENT_ID,
              "status": "partial_source_and_compatibility_pending", "candidates": alternatives}
    (HERE / "fallback-draft.json").write_text(json.dumps(output, indent=2) + "\n")
    return output


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal-offline", action="store_true")
    args = parser.parse_args()
    print("built", len(build(args.seal_offline)["candidates"]), "exact fallback engineering plans")
