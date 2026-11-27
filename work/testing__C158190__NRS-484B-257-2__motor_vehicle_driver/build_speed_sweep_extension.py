"""Stage three distinct source-gated speed cases without changing selected pairs.

The selected four-case manifest remains pinned until these additional cases have
their own offline, compatibility, saved and audit receipts. Requested speeds are
controller targets; original frozen-window measurements decide coverage.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name


def build() -> dict:
    plan_path = HERE / "judgment-probe-plan.json"
    plan = json.loads(plan_path.read_text())
    speed_ranges = [row for row in plan["ranges"] if row["range_index"] in (2, 5, 8)]
    if len(speed_ranges) != 3 or any(row["variable"] != "ego_speed" or
                                   row["status"] != "three_targets_planned_unmeasured"
                                   for row in speed_ranges):
        raise ValueError("three feasible frozen crossing-speed ranges required")
    first = speed_ranges[0]["planning_targets"]
    if any(row["planning_targets"] != first for row in speed_ranges[1:]):
        raise ValueError("frozen crossing-speed target bins differ across judgments")
    existing = json.loads((HERE / "case-plan.json").read_text())
    anchor = next(row for row in existing["cases"]
                  if row["case_id"].endswith("__approaching_near_response"))
    selected = json.loads((HERE / "execution-manifest.json").read_text())
    anchor_entry = next(row for row in selected["cases"]
                        if row["case_id"] == anchor["case_id"])
    station_ranges = [row for row in plan["ranges"] if row["range_index"] in (0, 3, 6)]
    if len(station_ranges) != 3 or any(row["variable"] != "counterpart_center_station"
                                   for row in station_ranges):
        raise ValueError("three feasible frozen station ranges required")
    station_targets = station_ranges[0]["planning_targets"]
    if any(row["planning_targets"] != station_targets for row in station_ranges[1:]):
        raise ValueError("station target bins differ across judgments")
    station_cases = {"below": "occupied_response", "inside": "approaching_near_response",
                     "above": "approaching_far_response"}
    station_bindings = []
    for bin_name, suffix in station_cases.items():
        case_id = ASSIGNMENT + "__" + suffix
        selected_case = next(row for row in selected["cases"] if row["case_id"] == case_id)
        planned_case = next(row for row in existing["cases"] if row["case_id"] == case_id)
        if planned_case["requested_other_station_m"] != station_targets[bin_name]:
            raise ValueError("selected station request differs from source-hashed target")
        station_bindings.append({"target_bin": bin_name, "case_id": case_id,
                                 "requested_station_m": station_targets[bin_name],
                                 "construction_sha256": selected_case["construction_sha256"]})
    extension = {"format": "c158190-source-gated-speed-extension-v1",
                 "assignment_id": ASSIGNMENT, "status": "construction_staged_proofs_pending",
                 "frozen_judgment_plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                 "selected_anchor_case_id": anchor["case_id"],
                 "selected_anchor_construction_sha256": anchor_entry["construction_sha256"],
                 "fixed_conditions": ["C158190 non-through intersection and reviewed yield device",
                                      "same other participant, approaching phase and requested station 8 m",
                                      "same route, camera plan, 20 Hz and 900 original frames"],
                 "deliberate_difference": "requested crossing-speed controller target; realized mean measured separately",
                 "station_range_indices_reused": [0, 3, 6],
                 "station_selected_bindings": station_bindings,
                 "speed_range_indices_reused": [2, 5, 8], "cases": []}
    for bin_name in ("below", "inside", "above"):
        value = first[bin_name]
        if type(value) not in (float, int) or value <= 0:
            raise ValueError("positive requested crossing-speed target required")
        variables = dict(anchor["draft_variables"])
        variables["requested_ego_crossing_speed_mps"] = value
        extension["cases"].append({
            "case_id": ASSIGNMENT + "__approaching_near_speed_" + bin_name,
            "target_bin": bin_name,
            "source_gated_site_requirement": "stop_site.validate_site with matching exact case_id",
            "construction_entrypoint": "speed_sweep_runner.py",
            "draft_variables": variables,
            "controller_contract": {"input": "requested_ego_crossing_speed_mps",
                                    "output": "Native ego throttle/brake request from measured speed",
                                    "acceptance": "original frozen mean from first body overlap through clearance"},
            "legal_judgment": None, "physical_acceptance_claimed": False})
    path = HERE / "speed-sweep-extension.json"
    path.write_text(json.dumps(extension, indent=2, ensure_ascii=False) + "\n")
    return {"case_ids": [row["case_id"] for row in extension["cases"]],
            "extension_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
