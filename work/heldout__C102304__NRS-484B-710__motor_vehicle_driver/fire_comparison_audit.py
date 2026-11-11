"""Independent CPU audit of NRS 484B.710 measured branch comparisons.

This compares retained measurement output, not expected legal labels. The source
hashes and frame observations are checked again so a summary cannot silently
substitute for the measured history. No tolerance is a statutory definition.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path


MEASUREMENTS = {"traveling_follow": "nearest_footprint_gap_ft",
                "stopped_drive_to": "centre_distance_ft",
                "stopped_park": "centre_distance_ft"}
BOUNDARY_BINS = {"below": "below_500_frames", "at": "at_500_frames",
                 "above": "above_500_frames"}
CONTEXT_KEYS = ("apparatus_answered_alarm", "authorized_emergency",
                "official_business")


def _measurement_engine():
    spec = importlib.util.spec_from_file_location("fire_branch", Path(__file__).with_name("fire_branch.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_case(row):
    case_id = row["case_id"]
    path = Path(row["measurement_path"])
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != row["measurement_sha256"]:
        raise ValueError(f"{case_id}: stale measurement hash")
    value = json.loads(raw)
    if value.get("branch") not in MEASUREMENTS:
        raise ValueError(f"{case_id}: unknown branch")
    if value.get("boundary_ft") != 500 or value.get("boundary_measurement") != MEASUREMENTS[value["branch"]]:
        raise ValueError(f"{case_id}: wrong boundary measurement")
    if value.get("frame_count", 0) <= 0 or value.get("active_frame_count", 0) <= 0:
        raise ValueError(f"{case_id}: missing measured frames")
    observations = value.get("observations")
    if not isinstance(observations, list) or len(observations) != value["frame_count"]:
        raise ValueError(f"{case_id}: incomplete observations")
    active = [item for item in observations if item.get("branch_active") is True]
    if len(active) != value["active_frame_count"]:
        raise ValueError(f"{case_id}: active frame count mismatch")
    tolerance = value.get("numerical_tolerance_ft")
    if type(tolerance) not in (int, float) or tolerance < 0 or tolerance > 1e-6:
        raise ValueError(f"{case_id}: invalid numerical reporting tolerance")
    boundary_key = MEASUREMENTS[value["branch"]]
    bins = {"below": [], "at": [], "above": []}
    for item in active:
        distance = item.get(boundary_key)
        if type(distance) not in (int, float) or distance < 0:
            raise ValueError(f"{case_id}: invalid measured distance")
        which = "below" if distance < 500 - tolerance else ("above" if distance > 500 + tolerance else "at")
        bins[which].append(item["frame"])
    for name, key in BOUNDARY_BINS.items():
        if bins[name] != value.get(key):
            raise ValueError(f"{case_id}: stale {name} frame classification")
    for source_kind in ("participant", "state"):
        source = Path(row[f"{source_kind}_path"])
        if sha256(source.read_bytes()).hexdigest() != value.get(f"{source_kind}_source_sha256"):
            raise ValueError(f"{case_id}: {source_kind} source hash mismatch")
    context = value.get("exception_context", {})
    fixed = {"branch": value["branch"],
             "apparatus_answered_alarm": value.get("apparatus_answered_alarm"),
             "authorized_emergency": context.get("authorized_emergency"),
             "official_business": context.get("official_business")}
    if any(type(fixed[key]) is not bool for key in CONTEXT_KEYS):
        raise ValueError(f"{case_id}: missing sourced context")
    if not context.get("source"):
        raise ValueError(f"{case_id}: missing alarm context source")
    sourced_context = {"alarm_response_source": context["source"],
                       "apparatus_answered_alarm": fixed["apparatus_answered_alarm"],
                       "subject_authorized_emergency": fixed["authorized_emergency"],
                       "subject_official_business": fixed["official_business"]}
    recomputed = _measurement_engine().measure_branch(
        row["participant_path"], row["state_path"], value["frame_count"],
        value["branch"], sourced_context)
    if recomputed != value:
        raise ValueError(f"{case_id}: measurement differs from retained sources")
    fixed["boundary_bin"] = tuple(name for name, frames in bins.items() if frames)
    return {"case_id": case_id, "bins": bins, "fixed": fixed,
            "measurement_sha256": sha256(raw).hexdigest()}


def audit(spec):
    """Audit two or more cases against an explicit fixed/difference contract."""
    cases = spec.get("cases")
    if not isinstance(cases, list) or len(cases) < 2:
        raise ValueError("Comparison needs at least two cases")
    measured = [_read_case(row) for row in cases]
    ids = [row["case_id"] for row in measured]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate case ID")
    fixed_keys = spec.get("fixed_conditions")
    if not isinstance(fixed_keys, list) or not fixed_keys or any(key not in (*CONTEXT_KEYS, "branch", "boundary_bin") for key in fixed_keys):
        raise ValueError("Invalid fixed conditions")
    differing_key = spec.get("deliberate_difference")
    if differing_key not in ("boundary_bin", "authorized_emergency", "official_business", "branch"):
        raise ValueError("Invalid deliberate difference")
    if differing_key in fixed_keys:
        raise ValueError("Difference also declared fixed")
    for key in fixed_keys:
        if len({row["fixed"][key] for row in measured}) != 1:
            raise ValueError(f"Fixed condition changed: {key}")
    expected = spec.get("expected_values")
    if not isinstance(expected, dict) or set(expected) != set(ids):
        raise ValueError("Expected differences must name every exact case")
    for row in measured:
        actual = row["bins"] if differing_key == "boundary_bin" else row["fixed"][differing_key]
        target = expected[row["case_id"]]
        if differing_key == "boundary_bin":
            if target not in BOUNDARY_BINS or not actual[target]:
                raise ValueError(f"{row['case_id']}: declared boundary bin absent")
        elif actual != target:
            raise ValueError(f"{row['case_id']}: declared difference absent")
    if len(set(json.dumps(value, sort_keys=True) for value in expected.values())) < 2:
        raise ValueError("Comparison does not vary its declared condition")
    return {"comparison_id": spec["comparison_id"], "passed": True,
            "cases": [{"case_id": row["case_id"],
                       "measurement_sha256": row["measurement_sha256"]} for row in measured],
            "fixed_conditions": fixed_keys, "deliberate_difference": differing_key}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(json.loads(args.spec.read_text())), sort_keys=True, indent=2))
