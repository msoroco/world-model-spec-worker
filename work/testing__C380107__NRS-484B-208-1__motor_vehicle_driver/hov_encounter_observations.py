"""Source-bound measurements for NRS 484B.208(1) and its HOV exception."""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C380107__NRS-484B-208-1__motor_vehicle_driver"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite original " + name + " required")
    return float(value)


def observe(case_id, context_path, trace_path, receipt_path):
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact case identity required")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if receipt.get("source_kind") != "original_native_capture" or receipt.get("diagnostic_fixture"):
        raise ValueError("original Native capture required")
    if (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("source receipt identity mismatch")
    if receipt.get("context_sha256") != digest(context_path) or receipt.get("trace_sha256") != digest(trace_path):
        raise ValueError("original source bytes changed")
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    if context.get("case_id") != case_id:
        raise ValueError("context case identity mismatch")
    for field in ("controlled_access_source", "lane_marking_source", "extreme_left_lane_source",
                  "posted_limit_source", "geographical_boundary_source", "driver_identity_source",
                  "motor_vehicle_source", "hov_designation_source", "hov_hours_source",
                  "hov_occupancy_rule_source", "hov_access_source", "hov_sign_source",
                  "hov_vehicle_category_source", "hov_compliance_source", "knowledge_circumstances_source",
                  "other_exceptions_source"):
        if not context.get(field):
            raise ValueError("original context source missing: " + field)
    lanes = context.get("same_direction_lane_ids")
    if not isinstance(lanes, list) or len(lanes) < 2 or any(not isinstance(x, str) or not x for x in lanes) or len(set(lanes)) != len(lanes):
        raise ValueError("two distinct marked same-direction lanes required")
    left_lane = context.get("extreme_left_lane_id")
    if left_lane not in lanes:
        raise ValueError("extreme-left lane identity required")
    limit = number(context.get("posted_limit_mps"), "posted limit")
    if limit <= 0:
        raise ValueError("positive posted limit required")
    if context.get("hov_designation_state") not in {"active", "inactive", "none"}:
        raise ValueError("source-backed HOV designation state required")
    if context.get("hov_compliance_state") not in {"compliant", "noncompliant", "unresolved"}:
        raise ValueError("source-backed HOV compliance state required")
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or receipt.get("fps") != 20 or receipt.get("frame_count") != len(rows):
        raise ValueError("original 20 Hz trace/frame count required")
    samples = []
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(number(row.get("time_s"), "time") - i / 20) > .002:
            raise ValueError("original frame cadence mismatch")
        ego_lane, rear_lane = row.get("ego_lane_id"), row.get("rear_lane_id")
        if ego_lane not in lanes or rear_lane not in lanes:
            raise ValueError("original lane identity missing")
        ego_speed = number(row.get("ego_speed_mps"), "ego speed")
        rear_speed = number(row.get("rear_speed_mps"), "rear speed")
        separation = number(row.get("rear_to_ego_signed_gap_m"), "signed gap")
        if ego_speed < 0 or rear_speed < 0:
            raise ValueError("nonnegative speeds required")
        samples.append({"frame": i, "time_s": row["time_s"], "ego_lane_id": ego_lane,
                        "rear_lane_id": rear_lane, "ego_speed_mps": ego_speed,
                        "rear_speed_mps": rear_speed, "rear_to_ego_signed_gap_m": separation,
                        "ego_below_posted_limit": ego_speed < limit,
                        "faster_rear_same_extreme_left_lane": ego_lane == rear_lane == left_lane and rear_speed > ego_speed})
    crossings = [samples[i]["frame"] for i in range(1, len(samples))
                 if samples[i - 1]["rear_to_ego_signed_gap_m"] > 0 >= samples[i]["rear_to_ego_signed_gap_m"]
                 and samples[i - 1]["faster_rear_same_extreme_left_lane"]]
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": digest(context_path), "trace_sha256": digest(trace_path),
                                "receipt_sha256": digest(receipt_path)},
            "posted_limit_mps": limit, "extreme_left_lane_id": left_lane,
            "hov_designation_state_source_label": context["hov_designation_state"],
            "hov_compliance_state_source_label": context["hov_compliance_state"],
            "first_rear_gap_crossing_frame": crossings[0] if crossings else None,
            "samples": samples, "knowledge_judgment": "unresolved",
            "continued_operation_judgment": "unresolved", "hov_legal_exception_judgment": "unresolved",
            "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "context", "trace", "receipt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    output = observe(args.case, args.context, args.trace, args.receipt)
    Path(args.output).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
