"""Review frozen judgment range targets without inventing legal thresholds."""

import hashlib
import json
from pathlib import Path

from saved_left_turn import ASSIGNMENT_ID


VARIABLE_CONTROLS = {
    "opposing_approach_speed": "initial opponent controller target speed; verify original 2..10 s mean",
    "opposing_boundary_relative_position": "initial opponent source waypoint offset; verify original body vertex at ego full entry",
    "opposing_stream_count": "distinct later opposite-direction actor spawns; verify original actor IDs",
    "opposing_vehicles_cleared_before_commit": "ego wait release after distinct opposing bodies clear; verify original commitment bracket",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review(ranges_path, plan_path, probe_path, expected_source_sha):
    ranges_path, plan_path, probe_path = Path(ranges_path), Path(plan_path), Path(probe_path)
    if sha(ranges_path) != expected_source_sha:
        raise ValueError("frozen judgment range source changed")
    ranges = json.loads(probe_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    cases = [case["case_id"] for case in plan["cases"]]
    if plan["assignment_id"] != ASSIGNMENT_ID or not cases or any(
            not case.startswith(ASSIGNMENT_ID + "__") for case in cases):
        raise ValueError("exact case plan identity changed")
    # The frozen payload groups set-specific ranges; preserve both source rows.
    rows = []
    for index, row in enumerate(ranges["ranges"]):
        variable = row["variable"]
        if variable not in VARIABLE_CONTROLS:
            raise ValueError("unmapped judgment observable: " + variable)
        if row["source_ref"]["sha256"] != expected_source_sha:
            raise ValueError("range row cites another source")
        targets = row["planning_targets"]
        feasible = {point: value for point, value in targets.items() if value is not None}
        impossible = [point for point, value in targets.items() if value is None]
        if impossible and not row["endpoint_limits"]:
            raise ValueError("missing frozen endpoint impossibility")
        rows.append({"range_index": index, "judgment_key": row["judgment_key"],
                     "variable": variable, "unit": row["unit"],
                     "source_bounds": [row["source_minimum"], row["source_maximum"]],
                     "targets_to_measure": feasible,
                     "unattainable_target_classes": impossible,
                     "endpoint_limits": row["endpoint_limits"],
                     "controller_or_spawn_knob": VARIABLE_CONTROLS[variable],
                     "candidate_case_ids": cases,
                     "witness_rule": "steady original Native source window; never startup transient or commanded value",
                     "status": "planning_only_unmeasured"})
    return {"format": "worker-source-bound-judgment-sweep-review",
            "assignment_id": ASSIGNMENT_ID,
            "range_source": str(ranges_path), "range_source_sha256": expected_source_sha,
            "case_plan_sha256": sha(plan_path), "rows": rows,
            "legal_cutoffs_inferred": False, "physical_coverage_claimed": False,
            "canonical_sweeps_expanded": False}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    package = Path(__file__).resolve().parent
    source = root / "inputs" / ASSIGNMENT_ID / "judgment_ranges.json"
    actual = sha(source)
    result = review(source, package / "case-plan.json", package / "judgment-probe-plan.json", actual)
    out = package / "physical-sweep-review.json"
    out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"{len(result['rows'])} source-bound range rows; targets remain unmeasured")
