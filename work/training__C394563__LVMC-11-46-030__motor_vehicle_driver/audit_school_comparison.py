"""Independent, source-bound comparison of the two school-warning cases.

The report compares measured Native-shaped inputs. It does not decide whether a
school lane, warning, child, release, or stop legally qualifies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from measure_school_warning import measure


ASSIGNMENT = "training__C394563__LVMC-11-46-030__motor_vehicle_driver"
CASES = (ASSIGNMENT + "__probe_1", ASSIGNMENT + "__probe_2")
CONTEXT_KEYS = (
    "native_map_sha256", "school_lane_geometry_sha256", "vehicle_extent_sha256",
    "warning_actor_sha256", "warning_state_source_sha256",
    "child_presence_source_sha256", "school_pedestrian_lane_survey",
    "nearest_lane_side_x_m", "vehicle_length_m",
)


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def audit(case_paths):
    if set(case_paths) != set(CASES):
        raise ValueError("Exact school-warning comparison cases missing")
    source = {}
    observed = {}
    for case_id in CASES:
        paths = case_paths[case_id]
        context_path, trace_path = Path(paths["context"]), Path(paths["trace"])
        context, rows = json.loads(context_path.read_text()), _rows(trace_path)
        if context.get("case_id") != case_id:
            raise ValueError("Original context case identity differs")
        result = measure(context, rows)
        if result["frame_count"] != 600 or result["rate_hz"] != 20:
            raise ValueError("Original 30-second capture incomplete")
        if result["first_stop_frame"] is None:
            raise ValueError("Original stop event missing")
        source[case_id] = {"context": context, "rows": rows,
                           "context_sha256": _digest(context_path),
                           "trace_sha256": _digest(trace_path)}
        observed[case_id] = result
    a, b = (source[case_id] for case_id in CASES)
    for key in CONTEXT_KEYS:
        if a["context"].get(key) != b["context"].get(key):
            raise ValueError("Fixed school-warning source differs: " + key)
    for index, (first, second) in enumerate(zip(a["rows"], b["rows"])):
        for key in ("warning_active", "children_about_to_cross_or_crossing",
                    "release_event", "source_cameras"):
            if first.get(key) != second.get(key):
                raise ValueError("Fixed warning or camera timeline differs: " + key +
                                 " at frame " + str(index))
    if observed[CASES[0]]["warning_role"] != observed[CASES[1]]["warning_role"]:
        raise ValueError("Fixed warning actor role differs")
    for key in ("first_release_event", "first_release_frame"):
        if observed[CASES[0]][key] != observed[CASES[1]][key]:
            raise ValueError("Fixed release policy differs: " + key)
    for case_id in CASES:
        rows = source[case_id]["rows"]
        if any(row.get("warning_role") != observed[case_id]["warning_role"] for row in rows):
            raise ValueError("Warning role not stationary")
    distance = [observed[case_id]["stop_distance_to_nearest_school_lane_side_ft"]["centre"]
                for case_id in CASES]
    if not distance[0] > distance[1]:
        raise ValueError("Measured stop-position distinction absent")
    if any(abs(distance[i] - target) > 2 for i, target in enumerate((55, 40))):
        raise ValueError("Requested and measured stop stations differ")
    return {"format": "worker-school-warning-comparison-audit",
            "comparison_id": ASSIGNMENT + "__comparison",
            "case_ids": list(CASES), "source_complete": True,
            "fixed_sources_checked": list(CONTEXT_KEYS) +
                ["warning_role", "first_release_event", "first_release_frame",
                 "warning_active_timeline", "child_warning_timeline",
                 "release_event_timeline", "source_camera_timeline"],
            "deliberate_difference": "measured_stop_centre_distance_to_school_lane_near_side_ft",
            "measured_stop_centre_ft": dict(zip(CASES, distance)),
            "source_hashes": {case_id: {key: source[case_id][key]
                                         for key in ("context_sha256", "trace_sha256")}
                              for case_id in CASES},
            "physical_completion": None, "legal_outcome": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-context", type=Path, required=True)
    parser.add_argument("--first-trace", type=Path, required=True)
    parser.add_argument("--second-context", type=Path, required=True)
    parser.add_argument("--second-trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit({CASES[0]: {"context": args.first_context, "trace": args.first_trace},
                    CASES[1]: {"context": args.second_context, "trace": args.second_trace}})
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
