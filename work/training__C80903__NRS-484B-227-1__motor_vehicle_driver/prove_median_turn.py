"""CPU source-shaped median-turn proof; fixture source hashes and motion invented."""

import hashlib
import json
from pathlib import Path

from measure_median_turn import CAMERAS, FRAMES, measure


def context():
    result = {"source_kind": "original_native_divided_highway_readback",
              "public_authority_opening_verified": True,
              "opening_x_m": [0.0, 10.0], "median_y_m": [-2.0, 2.0]}
    for index, name in enumerate(("native_map", "divider_geometry", "roadway_direction",
                                  "public_authority_opening", "vehicle_extent", "ego_pose_source"), 1):
        result[name + "_sha256"] = f"{index:x}" * 64
    return result


def trace(station=5.0):
    rows = []
    for i in range(FRAMES):
        if i <= 160:
            x, y = -30 + (station + 30) * i / 160, -5.0
        elif i <= 240:
            x, y = station, -5 + 10 * (i - 160) / 80
        else:
            x, y = station + 45 * (i - 240) / 359, 5.0
        road = "right_hand" if y < -2 else "opposite" if y > 2 else "median"
        rows.append({"video_frame": i, "native_frame": 200000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS},
                     "ego_center_x_m": x, "ego_center_y_m": y, "ego_width_m": 2.0,
                     "left_turn_active": 150 <= i <= 260, "u_turn_active": False,
                     "roadway_direction": road})
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    opening = measure(context(), trace(5.0))
    continuous = measure(context(), trace(18.0))
    assert opening["all_median_overlap_centers_within_authorized_opening"]
    assert opening["median_overlap_frames_outside_authorized_opening"] == 0
    assert not continuous["all_median_overlap_centers_within_authorized_opening"]
    assert continuous["median_overlap_frames_outside_authorized_opening"] > 0
    assert opening["legal_compliance"] == continuous["legal_compliance"] == "unassessed"
    negative = []
    source = context()
    source.pop("public_authority_opening_sha256")
    negative.append(reject("missing_authority_hash", source, trace(), "source hash"))
    source = context()
    source["public_authority_opening_verified"] = False
    negative.append(reject("unauthorized_opening", source, trace(), "Public-authority"))
    negative.append(reject("short_capture", context(), trace()[:-1], "Incomplete"))
    rows = trace()
    rows[300]["source_cameras"].pop("median_side")
    negative.append(reject("missing_camera", context(), rows, "Four source camera"))
    rows = trace()
    rows[300]["native_frame"] = rows[299]["native_frame"]
    negative.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace()
    for row in rows:
        row["left_turn_active"] = False
    negative.append(reject("no_turn", context(), rows, "No observed left turn"))
    rows = trace()
    for row in rows:
        row["ego_center_y_m"] = -5
    negative.append(reject("no_median_overlap", context(), rows, "No observed median"))
    proof = {"format": "worker-cpu-median-turn-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"opening": opening, "continuous_section": continuous}, "negative": negative}
    path = Path(__file__).with_name("median-turn-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
