"""CPU source-shaped median-turn proof; fixture source hashes and motion invented."""

import hashlib
import json
from pathlib import Path

from measure_median_turn import CAMERAS, FRAMES, measure


def context():
    result = {"source_kind": "original_native_divided_highway_readback",
              "public_authority_crossover_established": None,
              "opening_x_m": [0.0, 10.0], "median_y_m": [-2.0, 2.0]}
    for index, name in enumerate(("native_map", "divider_geometry", "roadway_direction",
                                  "physical_opening", "vehicle_extent", "ego_pose_source"), 1):
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
            x, y = station, 5.0 + 20 * (i - 240) / 359
        road = "right_hand" if y < -2 else "opposite" if y > 2 else "median"
        rows.append({"video_frame": i, "native_frame": 200000 + i, "time_s": i / 20,
                     "source_cameras": {name: 200000+i for name in CAMERAS},
                     "ego_center_x_m": x, "ego_center_y_m": y, "ego_width_m": 2.0,
                     "ego_length_m": 4.0, "observed_yaw_deg": 0.0 if i <= 150 else
                     90.0 if i >= 170 else (i-150)*4.5,
                     "left_turn_active": 150 <= i <= 260,
                     "semicircular_turn_active": False, "u_turn_active": False,
                     "roadway_direction": road})
    return rows


def turn_trace(mode, station=5.0):
    rows = trace(station)
    for row in rows:
        row['left_turn_active'] = mode == 'left_turn' and 150 <= row['video_frame'] <= 260
        row['semicircular_turn_active'] = mode == 'semicircular_turn' and 150 <= row['video_frame'] <= 260
        row['u_turn_active'] = mode == 'u_turn' and 150 <= row['video_frame'] <= 260
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
    assert opening["all_median_overlap_footprints_within_physical_opening"]
    assert opening["median_overlap_frames_outside_authorized_opening"] == 0
    assert not continuous["all_median_overlap_centers_within_authorized_opening"]
    assert not continuous["all_median_overlap_footprints_within_physical_opening"]
    assert continuous["median_overlap_frames_outside_authorized_opening"] > 0
    assert opening["legal_compliance"] == continuous["legal_compliance"] == "unassessed"
    semicircular = measure(context(), turn_trace('semicircular_turn'))
    u_turn = measure(context(), turn_trace('u_turn'))
    assert semicircular['observed_semicircular_turn'] and not semicircular['observed_left_turn']
    assert u_turn['observed_u_turn'] and not u_turn['observed_left_turn']
    near_edge = measure(context(), trace(9.0))
    assert near_edge['all_median_overlap_centers_within_authorized_opening']
    assert not near_edge['all_median_overlap_footprints_within_physical_opening']
    authority = context()
    authority['public_authority_crossover_established'] = True
    authority['public_authority_crossover_sha256'] = 'a' * 64
    assert measure(authority, trace(18.0))['public_authority_crossover_established'] is True
    negative = []
    source = context()
    source.pop("physical_opening_sha256")
    negative.append(reject("missing_opening_hash", source, trace(), "source hash"))
    source = context()
    source["public_authority_crossover_established"] = True
    negative.append(reject("missing_authority_hash_when_claimed", source, trace(), "source hash"))
    source = context()
    source["public_authority_crossover_established"] = "assumed"
    negative.append(reject("invalid_authority_disposition", source, trace(), "public-authority disposition"))
    negative.append(reject("short_capture", context(), trace()[:-1], "Incomplete"))
    rows = trace()
    rows[300]["source_cameras"].pop("reference_corner")
    negative.append(reject("missing_camera", context(), rows, "Four source camera"))
    rows = trace()
    rows[300]["native_frame"] = rows[299]["native_frame"]
    negative.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace()
    for row in rows:
        row["left_turn_active"] = False
    negative.append(reject("no_turn", context(), rows, "No observed turn"))
    rows = trace()
    for row in rows:
        row["ego_center_y_m"] = -5
    negative.append(reject("no_median_overlap", context(), rows, "No observed median"))
    rows = trace()
    rows[300].pop("ego_length_m")
    negative.append(reject("missing_vehicle_length", context(), rows, "ego length"))
    proof = {"format": "worker-cpu-median-turn-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"opening": opening, "continuous_section": continuous,
                          "semicircular": semicircular, "u_turn": u_turn,
                          "centre_inside_footprint_outside": near_edge,
                          "authority_crossover": measure(authority, trace(18.0))},
             "negative": negative}
    path = Path(__file__).with_name("median-turn-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
