"""Branch-specific interpretation of original raw measurements, without legal verdicts."""
import json
from pathlib import Path

from branch_variants import BRANCHES
from measure_entrance import measure


def validate_branch_measurement(measured, suffix):
    branch = BRANCHES[suffix]
    relation = "same" if branch.side == "same" else "opposite"
    sample_count = measured.get("stationary_sample_count")
    gap = (measured.get("stationary_min_gap_by_entrance_side_m") or {}).get(relation)
    if not isinstance(sample_count, int) or sample_count < 40:
        raise ValueError("At least two seconds of original stationary samples required")
    if not isinstance(gap, (int, float)) or gap < 0:
        raise ValueError("Original selected-side body gap missing")
    if measured.get("initial_activity") != branch.activity:
        raise ValueError("Cited stop, stand or park activity differs")
    if measured.get("exception_context") != branch.exception:
        raise ValueError("Cited exception context differs")
    if branch.exception == "traffic_conflict" and not measured.get("traffic_conflict_actor_observed"):
        raise ValueError("Original traffic-conflict actor evidence missing")
    if branch.exception == "police_officer" and not measured.get("police_direction_source_observed"):
        raise ValueError("Original police-direction source missing")
    if branch.exception == "official_device" and not measured.get("official_device_source_observed"):
        raise ValueError("Original official-device source missing")
    if branch.exception == "law" and not measured.get("applicable_law_source_reviewed"):
        raise ValueError("Applicable law source review missing")
    return {"selected_relation": relation, "raw_body_edge_gap_m": gap,
            "activity": branch.activity, "exception_context": branch.exception,
            "statutory_reference_point_method_adopted": False,
            "statutory_verdict": "unresolved"}


def measure_branch(attempt, suffix):
    """Read original source rows and reject missing branch-specific evidence."""
    attempt = Path(attempt)
    result = measure(attempt)
    context = json.loads((attempt / "entrance-context.json").read_text())
    rows = [json.loads(line) for line in (attempt / "native-vehicle.jsonl").read_text().splitlines()]
    if suffix == "traffic_conflict":
        others = [row.get("traffic_conflict_vehicle") for row in rows]
        result["traffic_conflict_actor_observed"] = all(
            isinstance(other, dict) and other.get("actor_id") != row.get("actor_id")
            and isinstance(other.get("body_xy_m"), list) and len(other["body_xy_m"]) >= 4
            for row, other in zip(rows, others))
    result["police_direction_source_observed"] = context.get("police_direction_source_observed") is True
    result["official_device_source_observed"] = context.get("official_device_source_observed") is True
    result["applicable_law_source_reviewed"] = context.get("applicable_law_source_reviewed") is True
    return validate_branch_measurement(result, suffix)
