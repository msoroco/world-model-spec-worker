"""CPU source-shaped diagnostics; no original Native rail-crossing evidence."""

import copy
import hashlib
import json
from pathlib import Path

from measure_rail import CAMERAS, FRAMES, measure


def context(space):
    return {"source_kind": "native_rail_vehicle_and_opposite_space_readback",
            "native_map_sha256": "1" * 64, "rail_geometry_sha256": "2" * 64,
            "vehicle_extent_sha256": "3" * 64,
            "opposite_space_source_sha256": "4" * 64,
            "crossing_kind": "at_grade", "entry_rail_x_m": 0.0,
            "clearance_reference_rail_x_m": 10.0, "vehicle_length_m": 4.0,
            "opposite_side_space_before_entry_m": space}


def trace(stop_center, cause):
    rows = []
    for i in range(FRAMES):
        center = -10 + (stop_center + 10) * i / 100 if i < 100 else stop_center
        rows.append({"video_frame": i, "native_frame": 15000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS},
                     "vehicle_center_x_m": center,
                     "observed_speed_mps": (stop_center + 10) / 5 if i < 100 else 0.0,
                     "stop_cause_source": cause if i >= 100 else None})
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    clear, short = measure(context(20), trace(17, None)), measure(context(2), trace(14, "opposite_space_observed"))
    boundary = measure(context(20), trace(16.572, None))
    just_short = measure(context(20), trace(16.571, None))
    grade_context = context(20)
    grade_context.update({"undercarriage_source_sha256": "5" * 64,
                          "minimum_undercarriage_clearance_m": 0.16,
                          "rail_grade_required_clearance_m": 0.24})
    grade = measure(grade_context, trace(14, "undercarriage_observed"))
    assert clear["trailing_end_reached_15_feet"] is True
    assert short["trailing_end_reached_15_feet"] is False
    assert clear["stopped_before_15_foot_clearance_frames"] == 0
    assert short["stopped_before_15_foot_clearance_frames"] > 0
    assert short["opposite_space_cause_observed_frames"] > 0
    assert boundary["trailing_end_reached_15_feet"] is True
    assert boundary["stopped_before_15_foot_clearance_frames"] == 0
    assert just_short["trailing_end_reached_15_feet"] is False
    assert just_short["stopped_before_15_foot_clearance_frames"] > 0
    assert grade["undercarriage_cause_observed_frames"] > 0
    assert abs(grade["undercarriage_clearance_alternative"]["clearance_deficit_m"] - 0.08) < 1e-12
    negative = []
    bad = copy.deepcopy(context(2))
    bad.pop("rail_geometry_sha256")
    negative.append(reject("missing_rail_source", bad, trace(14, None), "Missing source hash"))
    bad = copy.deepcopy(context(2))
    bad["crossing_kind"] = "overpass"
    negative.append(reject("not_at_grade", bad, trace(14, None), "At-grade"))
    bad = copy.deepcopy(context(2))
    bad["clearance_reference_rail_x_m"] = -1
    negative.append(reject("invalid_rail_order", bad, trace(14, None), "Invalid rail"))
    negative.append(reject("short_capture", context(2), trace(14, None)[:-1], "Incomplete 30-second"))
    bad_rows = trace(14, None)
    bad_rows[250]["source_cameras"].pop("rail_side")
    negative.append(reject("missing_camera", context(2), bad_rows, "Four source camera"))
    bad_rows = trace(14, None)
    bad_rows[250]["native_frame"] = bad_rows[249]["native_frame"]
    negative.append(reject("repeated_native_frame", context(2), bad_rows, "Native frame identity"))
    negative.append(reject("missing_undercarriage_source", context(20),
                           trace(14, "undercarriage_observed"), "Missing source hash: undercarriage"))
    bad = copy.deepcopy(grade_context)
    bad["rail_grade_required_clearance_m"] = 0.15
    negative.append(reject("no_undercarriage_deficit", bad,
                           trace(14, "undercarriage_observed"), "lacks sourced clearance deficit"))
    proof = {"format": "worker-cpu-rail-clearance-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"clear": clear, "short": short, "boundary": boundary,
                          "just_short": just_short, "grade": grade}, "negative": negative}
    path = Path(__file__).with_name("rail-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
