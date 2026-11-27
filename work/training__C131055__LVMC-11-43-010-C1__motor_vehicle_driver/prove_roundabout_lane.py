"""Synthetic source-shaped roundabout comparison and rejection proof."""

import hashlib
import json
import math
from pathlib import Path

from measure_roundabout_lane import CAMERAS, FRAMES, HASHES, measure
from roundabout_scene import LANES, intent, request, validate


def context(case="left_lane"):
    result = {"source_kind": "original_native_roundabout_readback",
              "roundabout_topology_verified": True, "exit_intention_sourced": True,
              "exit_intent": intent(case),
              "left_lane_center_radius_m": 12, "right_lane_center_radius_m": 16,
              "lane_half_width_m": 1.5}
    for name in HASHES:
        result[name + "_sha256"] = hashlib.sha256(("synthetic-fixture:" + name).encode()).hexdigest()
    return result


def trace(case):
    radius = LANES[case]
    turn = intent(case)
    sweep = 2 * math.pi if turn == "u_turn" else 3 * math.pi / 2
    rows = []
    for i in range(FRAMES):
        if i < 100:
            phase, x, y, heading, theta = "entry", 0, -40 + (40 - radius) * i / 100, 90, None
        elif i <= 400:
            theta = -math.pi / 2 + (i - 100) * sweep / 300
            phase, x, y, heading = "circulation", radius * math.cos(theta), radius * math.sin(theta), (math.degrees(theta) + 90) % 360
        else:
            if turn == "u_turn":
                phase, x, y, heading, theta = "exit", 0, -radius - (i - 400) * 0.1, 270, None
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
    left = measure(context("left_lane"), trace("left_lane"))
    right = measure(context("right_lane"), trace("right_lane"))
    u_left = measure(context("u_turn_left_lane"), trace("u_turn_left_lane"))
    u_right = measure(context("u_turn_right_lane"), trace("u_turn_right_lane"))
    assert left["left_lane_frame_count"] == right["right_lane_frame_count"] == 301
    assert left["right_lane_frame_count"] == right["left_lane_frame_count"] == 0
    assert left["lane_change_count"] == right["lane_change_count"] == 0
    assert left["legal_compliance"] == right["legal_compliance"] == "unassessed"
    assert u_left["left_lane_frame_count"] == u_right["right_lane_frame_count"] == 301
    assert u_left["exit_intent"] == u_right["exit_intent"] == "u_turn"
    negatives = []
    source = context()
    source.pop("roundabout_lanes_sha256")
    negatives.append(reject("missing_lane_source", source, trace("left_lane"), "source hash"))
    source = context()
    source["exit_intention_sourced"] = False
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
    negatives.append(reject("wrong_exit", context(), rows, "Sourced exit trajectory"))
    rows = trace("u_turn_left_lane")
    for row in rows:
        if row["phase"] == "exit":
            row["ego_heading_deg"] = 180
    negatives.append(reject("u_turn_wrong_exit", context("u_turn_left_lane"), rows,
                            "Sourced exit trajectory"))
    proof = {"format": "worker-cpu-roundabout-lane-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "scenes": scenes,
             "positive": {"left_lane": left, "right_lane": right,
                          "u_turn_left_lane": u_left, "u_turn_right_lane": u_right},
             "negative": negatives}
    path = Path(__file__).with_name("roundabout-lane-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negatives),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
