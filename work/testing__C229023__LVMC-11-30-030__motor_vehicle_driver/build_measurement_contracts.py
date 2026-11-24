"""Write draft source-bound measurement contracts for the six exact cases."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from case_construction import CASES
from crosswalk_measurements import ASSIGNMENT_ID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = Path("inputs") / ASSIGNMENT_ID / "assignment.json"


def build() -> list[Path]:
    plan = json.loads((HERE / "case-plan.json").read_text())
    if plan.get("assignment_id") != ASSIGNMENT_ID:
        raise ValueError("exact assignment plan required")
    cases = {row["case_id"]: row for row in plan["cases"]}
    expected = {ASSIGNMENT_ID + "__" + suffix for suffix in CASES}
    if set(cases) != expected:
        raise ValueError("all six exact crosswalk cases required")
    source_hash = hashlib.sha256((ROOT / SOURCE).read_bytes()).hexdigest()
    branch = plan["selected_branches"][0]
    assignment = json.loads((ROOT / SOURCE).read_text())
    if assignment.get("law", {}).get("text") != plan.get("law_text") or branch["source_index"] != 281:
        raise ValueError("exact exported law or selected witness changed")
    written = []
    for case_id in sorted(expected):
        row = cases[case_id]
        suffix = case_id.removeprefix(ASSIGNMENT_ID + "__")
        crossing, behavior, purpose = CASES[suffix]
        if (row["crosswalk_kind"], row["ego_maneuver_request"],
                row["stopped_vehicle_purpose_claim"]) != (crossing, behavior, purpose):
            raise ValueError("exact case dimensions changed")
        contract = {
            "format": "worker-measurement-contract",
            "status": "draft_unselected",
            "case_id": case_id,
            "requirements": [{
                "disposition_index": 0,
                "requirement": plan["law_text"],
                "source": {"path": str(SOURCE), "sha256": source_hash,
                           "source_locator": "law.text"},
                "kind": "measured",
                "method": "measure_crosswalk_observation",
                "output_key": "crosswalk_observation",
                "value_type": "object",
                "inputs": ["context.json", "trace.jsonl", "frame-map.jsonl",
                           "receipt.json", "overview.mkv", "approach.mkv",
                           "reference_corner.mkv", "driver_reference.mkv"],
            }],
            "exact_target": {"crosswalk_kind": crossing,
                             "ego_maneuver_request": behavior,
                             "stopped_vehicle_purpose_claim": purpose},
            "measured_keys": ["observed.rear_approach_sampled",
                              "observed.lead_stop_sampled",
                              "observed.pedestrian_in_polygon_sampled",
                              "observed.ego_full_pass_sampled"],
            "negative": {"remove": ["context.json"],
                         "error_contains": "Missing required source: context.json"},
            "unresolved_judgments": [
                "original road intersection and crosswalk status",
                "lead stopped to permit this pedestrian",
                "rear approach and overtaking under the statutory language",
                "physical camera visibility and crossing completion",
            ],
        }
        target = HERE / "cases" / suffix / "measurement-contract.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(contract, indent=2) + "\n")
        written.append(target)
    return written


if __name__ == "__main__":
    print("built", len(build()), "exact draft measurement contracts")
