"""Source-bound motion, lamp and photometry observations for LVMC 11.38.120.

This does not infer legal visibility or covered-vehicle status from appearance.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C230286__LVMC-11-38-120-B__motorcycle_or_moped_operator"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite_nonnegative(value):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("finite nonnegative original measurement required")
    return value


def measure(case_id, context_path, trace_path, receipt_path):
    if not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact assignment case required")
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    if (receipt.get("assignment_id"), receipt.get("case_id")) != (ASSIGNMENT_ID, case_id):
        raise ValueError("original source receipt identity mismatch")
    if receipt.get("diagnostic_fixture") or receipt.get("source_kind") != "original_native_capture":
        raise ValueError("original Native capture required")
    if receipt.get("context_sha256") != sha(context_path) or receipt.get("trace_sha256") != sha(trace_path):
        raise ValueError("original source bytes changed")
    context = json.loads(Path(context_path).read_text(encoding="utf-8"))
    if context.get("case_id") != case_id or not isinstance(context.get("map_sha256"), str) or len(context["map_sha256"]) != 64:
        raise ValueError("exact source map context required")
    for key in ("vehicle_blueprint_source", "section_080_coverage_source", "trail_ride_source",
                "enclosed_three_wheel_source", "road_sidewalk_source", "local_date_time_source",
                "sunset_sunrise_source", "light_atmosphere_source", "discernibility_500ft_source",
                "headlamp_calibration_source", "tail_lamp_calibration_source"):
        if not context.get(key):
            raise ValueError("original context source missing: " + key)
    for key in ("local_datetime", "sunset_local", "sunrise_local"):
        if not isinstance(context.get(key), str) or not context[key]:
            raise ValueError("original local timing missing: " + key)
    head, tail = context.get("headlamp_calibration"), context.get("tail_lamp_calibration")
    if not isinstance(head, dict) or not isinstance(tail, dict):
        raise ValueError("original calibrated lamp inventory required")
    for lamp in (head, tail):
        if lamp.get("emitted_color") not in {"white", "red", "other"} or not isinstance(lamp.get("mounted_position"), str):
            raise ValueError("original lamp color and mount required")
        finite_nonnegative(lamp.get("tested_visibility_ft"))
    discernibility = finite_nonnegative(context.get("observed_discernibility_ft"))
    if head.get("mounted_position") != "front" or tail.get("mounted_position") != "rear":
        raise ValueError("front headlamp and rear tail lamp required")
    rows = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
    if len(rows) < 2 or len(rows) != receipt.get("frame_count") or receipt.get("fps") != 20:
        raise ValueError("original 20 Hz frame count mismatch")
    observations = []
    for index, row in enumerate(rows):
        if row.get("frame") != index or not isinstance(row.get("time_s"), (int, float)) or abs(row["time_s"] - index / 20) > .002:
            raise ValueError("original frame cadence mismatch")
        speed = finite_nonnegative(row.get("speed_mps"))
        if type(row.get("headlamp_burning")) is not bool or type(row.get("tail_lamp_burning")) is not bool:
            raise ValueError("independent original lamp burning states required")
        observations.append({"frame": index, "time_s": row["time_s"], "speed_mps": speed,
                             "headlamp_burning": row["headlamp_burning"],
                             "tail_lamp_burning": row["tail_lamp_burning"]})
    return {"assignment_id": ASSIGNMENT_ID, "case_id": case_id,
            "source_bindings": {"context_sha256": sha(context_path), "trace_sha256": sha(trace_path),
                                "receipt_sha256": sha(receipt_path), "native_map_sha256": context["map_sha256"]},
            "original_local_timing": {k: context[k] for k in ("local_datetime", "sunset_local", "sunrise_local")},
            "calibrated_headlamp": head, "calibrated_tail_lamp": tail,
            "observed_discernibility_ft": discernibility, "observations": observations,
            "headlamp_300ft_reference_only": 300, "tail_lamp_500ft_reference_only": 500,
            "half_hour_offset_minutes_reference_only": 30,
            "covered_vehicle_judgment": "unresolved", "visibility_judgment": "unresolved",
            "burning_requirement_judgment": "unresolved", "physical_acceptance": "unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("case", "context", "trace", "receipt", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    result = measure(args.case, args.context, args.trace, args.receipt)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
