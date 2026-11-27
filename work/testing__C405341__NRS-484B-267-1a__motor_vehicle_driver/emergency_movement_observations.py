"""Original-source motion and visibility observations for NRS 484B.267(1)(a)."""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C405341__NRS-484B-267-1a__motor_vehicle_driver"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite original " + label + " required")
    return float(value)


def xy(raw, label):
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError("original " + label + " coordinate pair required")
    return (finite(raw[0], label), finite(raw[1], label))


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
    for key in ("subject_driver_source", "subject_vehicle_source", "approach_route_source",
                "emergency_or_official_status_source", "regulatory_agency_source",
                "flashing_equipment_qualification_source", "light_use_source",
                "driver_view_camera_source", "visibility_annotation_source",
                "vehicle_movement_source", "hand_signal_source", "officer_direction_source",
                "subject_control_source"):
        if not context.get(key):
            raise ValueError("original context source missing: " + key)
    if context.get("target_vehicle_class") not in {"authorized_emergency", "regulatory_official", "other"}:
        raise ValueError("source-backed target vehicle class required")
    if context.get("light_qualification_state") not in {"qualified", "unqualified", "unresolved"}:
        raise ValueError("source-backed flashing-light qualification state required")
    if context.get("officer_direction_state") not in {"none", "directed", "unresolved"}:
        raise ValueError("source-backed officer direction state required")
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or receipt.get("fps") != 20 or receipt.get("frame_count") != len(rows):
        raise ValueError("original 20 Hz trace/frame count required")
    samples = []
    prior_position = None
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(finite(row.get("time_s"), "time") - i / 20) > .002:
            raise ValueError("original frame cadence mismatch")
        ego = xy(row.get("ego_position_xy_m"), "ego")
        target = xy(row.get("target_position_xy_m"), "target")
        if not isinstance(row.get("flashing_lights_active"), bool) or not isinstance(row.get("movement_visible_in_driver_view"), bool) or not isinstance(row.get("hand_signal_visible_in_driver_view"), bool):
            raise ValueError("original light and driver-view annotations required")
        ego_speed = finite(row.get("ego_speed_mps"), "ego speed")
        if ego_speed < 0:
            raise ValueError("nonnegative ego speed required")
        movement = None if prior_position is None else math.dist(prior_position, target)
        prior_position = target
        samples.append({"frame": i, "time_s": row["time_s"], "ego_position_xy_m": list(ego),
                        "target_position_xy_m": list(target), "ego_speed_mps": ego_speed,
                        "ego_target_center_distance_m": math.dist(ego, target),
                        "target_interframe_displacement_m": movement,
                        "flashing_lights_active": row["flashing_lights_active"],
                        "movement_visible_in_driver_view": row["movement_visible_in_driver_view"],
                        "hand_signal_visible_in_driver_view": row["hand_signal_visible_in_driver_view"]})
    visible_movement = [s["frame"] for s in samples if s["target_interframe_displacement_m"] is not None
                        and s["target_interframe_displacement_m"] > 0
                        and s["movement_visible_in_driver_view"]]
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": digest(context_path), "trace_sha256": digest(trace_path),
                                "receipt_sha256": digest(receipt_path)},
            "target_vehicle_class_source_label": context["target_vehicle_class"],
            "light_qualification_source_label": context["light_qualification_state"],
            "officer_direction_source_label": context["officer_direction_state"],
            "first_visible_nonzero_movement_frame": visible_movement[0] if visible_movement else None,
            "samples": samples, "about_to_move_judgment": "unresolved",
            "proceed_with_caution_judgment": "unresolved", "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "context", "trace", "receipt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = observe(args.case, args.context, args.trace, args.receipt)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
