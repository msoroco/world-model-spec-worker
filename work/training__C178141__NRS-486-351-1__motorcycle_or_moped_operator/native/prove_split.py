"""Source-shaped CPU diagnostics; no original Native motorcycle observation."""

import copy
import hashlib
import json
from pathlib import Path

from measure_split import CAMERAS, FRAMES, measure


def context():
    return {"source_kind": "native_adjacent_lane_and_actor_readback",
            "native_map_sha256": "1" * 64, "lane_adjacency_sha256": "2" * 64,
            "motorcycle_identity_sha256": "3" * 64,
            "left_vehicle_identity_sha256": "4" * 64,
            "right_vehicle_identity_sha256": "5" * 64,
            "police_duty_source_sha256": "6" * 64,
            "subject_is_police_officer": False, "subject_performing_police_duty": False,
            "subject_kind": "motorcycle", "adjacent_lane_ids": ["lane_left", "lane_right"]}


def trace(subject_y, surrounding_speed=0.0):
    rows = []
    for i in range(FRAMES):
        x = -30 + i * 0.1
        other_x = x if surrounding_speed > 0 else 0.0
        rows.append({"video_frame": i, "native_frame": 7000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS},
                     "left_vehicle_lane_id": "lane_left", "right_vehicle_lane_id": "lane_right",
                     "subject_footprint_m": {"min_x": x - 1, "max_x": x + 1,
                                             "min_y": subject_y - 0.4, "max_y": subject_y + 0.4},
                     "left_vehicle_footprint_m": {"min_x": other_x - 2, "max_x": other_x + 2,
                                                  "min_y": 0.8, "max_y": 2.2},
                     "right_vehicle_footprint_m": {"min_x": other_x - 2, "max_x": other_x + 2,
                                                   "min_y": 3.8, "max_y": 5.2},
                     "left_vehicle_speed_mps": surrounding_speed,
                     "right_vehicle_speed_mps": surrounding_speed})
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    source = context()
    beside, between = trace(1.5), trace(3.0)
    a, b = measure(source, beside), measure(source, between)
    moving = measure(source, trace(3.0, 2.0))
    assert a["between_vehicle_frames"] == 0
    assert 0 < b["between_vehicle_frames"] < FRAMES
    assert moving["between_vehicle_frames"] == FRAMES
    assert b["left_vehicle_speed_mps_range"] == [0.0, 0.0]
    assert moving["left_vehicle_speed_mps_range"] == [2.0, 2.0]
    moped_source = copy.deepcopy(source)
    moped_source["subject_kind"] = "moped"
    moped = measure(moped_source, between)
    assert moped["subject_kind_source_claim"] == "moped"
    assert moped["between_vehicle_frames"] == b["between_vehicle_frames"]
    police_source = copy.deepcopy(source)
    police_source["subject_is_police_officer"] = True
    police_source["subject_performing_police_duty"] = True
    police = measure(police_source, between)
    assert police["police_officer_performing_duty_source_claim"] is True
    assert police["between_vehicle_frames"] == b["between_vehicle_frames"]
    assert police["legal_compliance"] == "unassessed"
    negative = []
    bad = copy.deepcopy(source)
    bad.pop("lane_adjacency_sha256")
    negative.append(reject("missing_lane_source", bad, between, "Missing source hash"))
    bad = copy.deepcopy(source)
    bad["adjacent_lane_ids"] = ["lane_left", "lane_left"]
    negative.append(reject("not_adjacent", bad, between, "Adjacent traffic lanes"))
    bad = copy.deepcopy(source)
    bad.pop("police_duty_source_sha256")
    negative.append(reject("missing_police_duty_source", bad, between, "Police-duty source hash"))
    bad = copy.deepcopy(source)
    bad["subject_performing_police_duty"] = True
    negative.append(reject("duty_without_officer", bad, between, "Police-officer duty identity"))
    negative.append(reject("short_capture", source, between[:-1], "Incomplete 30-second"))
    bad_rows = copy.deepcopy(between)
    bad_rows[250]["right_vehicle_lane_id"] = "lane_left"
    negative.append(reject("vehicle_wrong_lane", source, bad_rows, "do not occupy sourced adjacent lanes"))
    bad_rows = copy.deepcopy(between)
    bad_rows[250]["source_cameras"].pop("lane_side")
    negative.append(reject("missing_camera", source, bad_rows, "Four source camera"))
    bad_rows = copy.deepcopy(between)
    bad_rows[250]["native_frame"] = bad_rows[249]["native_frame"]
    negative.append(reject("repeated_native_frame", source, bad_rows, "Native frame identity"))
    proof = {"format": "worker-cpu-adjacent-vehicle-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"beside": a, "between_stationary": b, "between_moving": moving},
             "alternative_diagnostics": {"moped_between_stationary": moped,
                                         "police_duty_between_stationary": police},
             "negative": negative}
    path = Path(__file__).with_name("split-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
