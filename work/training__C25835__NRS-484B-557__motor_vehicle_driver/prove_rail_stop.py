"""CPU source-shaped proof; fixture motion is not original Native evidence."""

import copy
import hashlib
import json
from pathlib import Path

from rail_stop_measure import CAMERAS, FRAME_COUNT, measure


def context():
    return {
        "source_kind": "native_grade_crossing_readback",
        "map_sha256": "1" * 64,
        "rail_geometry_sha256": "2" * 64,
        "vehicle_extent_sha256": "3" * 64,
        "official_sign_source_sha256": "4" * 64,
        "designation_source_sha256": "5" * 64,
        "occluder_geometry_sha256": "6" * 64,
        "crossing_kind": "highway_rail_at_grade",
        "sign_governs": "rail_crossing_approach",
        "designation_authority": "department_of_transportation",
        "nearest_track_approach_edge_x_m": 0.0,
        "vehicle_length_m": 4.0,
    }


def trace(stop_center):
    rows = []
    for i in range(FRAME_COUNT):
        if i < 150:
            center = -30 + (stop_center + 30) * i / 150
            speed = (stop_center + 30) / 7.5
        elif i < 210:
            center, speed = stop_center, 0.0
        elif i < 340:
            center = stop_center + (12 - stop_center) * (i - 210) / 130
            speed = (12 - stop_center) / 6.5
        else:
            center, speed = 12.0, 0.0
        rows.append({
            "video_frame": i, "native_frame": 10000 + i, "time_s": i / 20,
            "source_cameras": {name: i for name in CAMERAS},
            "vehicle_center_x_m": center,
            "observed_speed_mps": speed,
            "rail_approach_visibility": "occluded" if i < 210 else "clear",
            "train_state": "none_observed",
        })
    return rows


def rejects(label, ctx, rows, expected):
    try:
        measure(ctx, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    # Centre targets approximate 25 ft and 10 ft. Report all measured reference
    # points; do not equate a centre target with a legal boundary verdict.
    inside = measure(context(), trace(-25 / 3.280839895013123))
    near = measure(context(), trace(-10 / 3.280839895013123))
    assert 24.5 < inside["stop_reference_distances_from_nearest_track_ft"]["center_ft"] < 25.5
    assert 9.5 < near["stop_reference_distances_from_nearest_track_ft"]["center_ft"] < 10.5
    assert inside["first_stop_frame"] == near["first_stop_frame"] == 151
    negative = []
    ctx = context()
    ctx.pop("designation_source_sha256")
    negative.append(rejects("missing_designation", ctx, trace(-7), "Missing source hash"))
    ctx = context()
    ctx["sign_governs"] = "separate_intersection"
    negative.append(rejects("wrong_sign_governance", ctx, trace(-7), "governance"))
    ctx = context()
    ctx["crossing_kind"] = "overpass"
    negative.append(rejects("not_grade_crossing", ctx, trace(-7), "grade crossing"))
    negative.append(rejects("short_capture", context(), trace(-7)[:-1], "Incomplete 30-second"))
    rows = trace(-7)
    rows[250]["source_cameras"].pop("rail_side")
    negative.append(rejects("missing_source_camera", context(), rows, "Four source camera"))
    rows = trace(-7)
    rows[250]["native_frame"] = rows[249]["native_frame"]
    negative.append(rejects("duplicate_native_frame", context(), rows, "Native frame identity"))
    rows = trace(-7)
    rows[180]["rail_approach_visibility"] = None
    negative.append(rejects("missing_visibility", context(), rows, "rail visibility"))
    rows = trace(-7)
    for row in rows:
        row["observed_speed_mps"] = 2.0
    negative.append(rejects("rolling_stop", context(), rows, "complete cessation"))
    proof = {
        "format": "worker-cpu-rail-stop-proof", "passed": True,
        "diagnostic_only": True, "original_native_observed": False,
        "positive": {"center_25_ft": inside, "center_10_ft": near},
        "negative": negative,
    }
    path = Path(__file__).with_name("rail-stop-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
