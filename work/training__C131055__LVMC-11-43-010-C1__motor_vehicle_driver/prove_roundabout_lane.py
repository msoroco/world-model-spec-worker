"""Synthetic source-shaped roundabout comparison and rejection proof."""

import hashlib
import json
import math
from pathlib import Path

from measure_roundabout_lane import CAMERAS, FRAMES, HASHES, measure
from roundabout_scene import LANES, request, validate


def context():
    result = {"source_kind": "original_native_roundabout_readback",
              "roundabout_topology_verified": True, "left_exit_intention_sourced": True,
              "left_lane_center_radius_m": 12, "right_lane_center_radius_m": 16,
              "lane_half_width_m": 1.5}
    for name in HASHES:
        result[name + "_sha256"] = hashlib.sha256(("synthetic-fixture:" + name).encode()).hexdigest()
    return result


def trace(case):
    radius = LANES[case]
    rows = []
    for i in range(FRAMES):
        if i < 100:
            phase, x, y, heading, theta = "entry", 0, -40 + (40 - radius) * i / 100, 90, None
        elif i <= 400:
            theta = -math.pi / 2 + (i - 100) * (3 * math.pi / 2) / 300
            phase, x, y, heading = "circulation", radius * math.cos(theta), radius * math.sin(theta), (math.degrees(theta) + 90) % 360
        else:
            phase, x, y, heading, theta = "exit", -radius - (i - 400) * 0.1, 0, 180, None
        rows.append({"video_frame": i, "native_frame": 700000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS}, "phase": phase,
                     "ego_x_m": x, "ego_y_m": y, "ego_heading_deg": heading,
                     "unwrapped_angle_rad": theta})
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(label + " unexpectedly passed")


if __name__ == "__main__":
    scenes = {case: validate(request(case)) for case in LANES}
    left = measure(context(), trace("left_lane"))
    right = measure(context(), trace("right_lane"))
    assert left["left_lane_frame_count"] == right["right_lane_frame_count"] == 301
    assert left["right_lane_frame_count"] == right["left_lane_frame_count"] == 0
    assert left["lane_change_count"] == right["lane_change_count"] == 0
    assert left["legal_compliance"] == right["legal_compliance"] == "unassessed"
    negatives = []
    source = context()
    source.pop("roundabout_lanes_sha256")
    negatives.append(reject("missing_lane_source", source, trace("left_lane"), "source hash"))
    source = context()
    source["left_exit_intention_sourced"] = False
    negatives.append(reject("unsourced_intention", source, trace("left_lane"), "intention"))
    negatives.append(reject("short_capture", context(), trace("left_lane")[:-1], "Incomplete"))
    rows = trace("left_lane")
    rows[200]["source_cameras"].pop("exit_lane")
    negatives.append(reject("missing_camera", context(), rows, "camera"))
    rows = trace("left_lane")
    rows[200]["native_frame"] = rows[199]["native_frame"]
    negatives.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace("left_lane")
    rows[200]["ego_x_m"] = 100
    negatives.append(reject("outside_ring", context(), rows, "inventoried lanes"))
    rows = trace("left_lane")
    for row in rows:
        if row["phase"] == "exit":
            row["ego_heading_deg"] = 0
    negatives.append(reject("wrong_exit", context(), rows, "Left-turn exit"))
    proof = {"format": "worker-cpu-roundabout-lane-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "scenes": scenes, "positive": {"left_lane": left, "right_lane": right}, "negative": negatives}
    path = Path(__file__).with_name("roundabout-lane-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negatives),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
