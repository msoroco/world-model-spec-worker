"""Source-bound stop-distance and human-warning observations for LVMC 11.46.030."""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C422976__LVMC-11-46-030__motor_vehicle_driver"
FEET_PER_METER = 1 / 0.3048


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite original " + label + " required")
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
    for key in ("municipal_jurisdiction_source", "school_pedestrian_lane_source",
                "nearest_side_geometry_source", "ego_connected_approach_source",
                "road_lane_identity_source", "responsible_person_source", "vehicle_source",
                "stationed_person_identity_source", "human_warning_source",
                "children_presence_source", "human_signal_source", "person_location_source",
                "vehicle_body_reference_source", "driver_view_camera_source"):
        if not context.get(key):
            raise ValueError("original context source missing: " + key)
    nearest_side = finite(context.get("school_lane_nearest_side_station_m"), "school lane nearest-side station")
    if context.get("vehicle_reference_point") not in {"front_body_extent", "center", "rear_body_extent"}:
        raise ValueError("original vehicle reference point required")
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or receipt.get("fps") != 20 or receipt.get("frame_count") != len(rows):
        raise ValueError("original 20 Hz frame count required")
    samples = []
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(finite(row.get("time_s"), "time") - i / 20) > .002:
            raise ValueError("original frame cadence mismatch")
        speed = finite(row.get("ego_speed_mps"), "ego speed")
        if speed < 0:
            raise ValueError("nonnegative ego speed required")
        station = finite(row.get("ego_reference_station_m"), "ego reference station")
        for key in ("human_warning_active", "person_stationed", "children_about_to_cross_or_crossing",
                    "human_go_signal", "human_left_locality", "device_signal_stopped_raised_or_removed"):
            if not isinstance(row.get(key), bool):
                raise ValueError("original human/device annotation required: " + key)
        samples.append({"frame": i, "time_s": row["time_s"], "ego_speed_mps": speed,
                        "ego_reference_station_m": station,
                        "reference_to_nearest_side_distance_ft": (nearest_side - station) * FEET_PER_METER,
                        "complete_cessation_sample": speed == 0,
                        **{key: row[key] for key in ("human_warning_active", "person_stationed",
                            "children_about_to_cross_or_crossing", "human_go_signal", "human_left_locality",
                            "device_signal_stopped_raised_or_removed")}})
    zero_frames = [row["frame"] for row in samples if row["complete_cessation_sample"]]
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": digest(context_path), "trace_sha256": digest(trace_path),
                                "receipt_sha256": digest(receipt_path)},
            "school_lane_nearest_side_station_m": nearest_side,
            "vehicle_reference_point_source_label": context["vehicle_reference_point"],
            "first_zero_speed_frame": zero_frames[0] if zero_frames else None,
            "samples": samples, "fifty_foot_legal_measurement_convention": "unresolved",
            "stopped_not_less_than_fifty_feet_judgment": "unresolved",
            "proceed_after_release_judgment": "unresolved", "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "context", "trace", "receipt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = observe(args.case, args.context, args.trace, args.receipt)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
