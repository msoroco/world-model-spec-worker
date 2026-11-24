"""CPU source-shaped tunnel proof; sample motion is synthetic, not Native."""

import copy
import hashlib
import json
from pathlib import Path

from measure_tunnel import CAMERAS, FRAMES, measure


def context(*, one_way=False):
    return {
        "source_kind": "original_native_tunnel_map_and_ray_readback",
        "native_map_sha256": "1" * 64,
        "portal_geometry_sha256": "2" * 64,
        "road_direction_survey_sha256": "3" * 64,
        "centreline_geometry_sha256": "4" * 64,
        "vehicle_extent_sha256": "5" * 64,
        "sight_ray_source_sha256": "6" * 64,
        "structure_kind": "tunnel", "approach_portal_x_m": 0.0,
        "highway_centre_y_m": 0.0,
        "one_way_native_survey": one_way,
    }


def trace(*, left=False):
    rows = []
    y = 2.2 if left else -2.2
    for i in range(FRAMES):
        x = -65 + 80 * i / 400 if i < 400 else 15.0
        speed = 4.0 if i < 400 else 0.0
        body = [[x - 2, y - 0.9], [x + 2, y - 0.9],
                [x + 2, y + 0.9], [x - 2, y + 0.9]]
        rows.append({
            "video_frame": i, "native_frame": 8000 + i, "time_s": i / 20,
            "source_cameras": {name: i for name in CAMERAS},
            "body_xy_m": body, "observed_speed_mps": speed,
            "incoming_lane_sight_ray": {"status": "blocked", "clear_lower_bound_m": 18,
                                         "blocker_upper_bound_m": 21},
        })
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    right = measure(context(), trace())
    left = measure(context(), trace(left=True))
    one_way = measure(context(one_way=True), trace(left=True))
    assert right["within_100_ft_driving_frames"] > 0
    assert right["left_and_blocked_within_zone_frames"] == 0
    assert left["left_and_blocked_within_zone_frames"] > 0
    assert one_way["one_way_highway_surveyed"] is True
    assert one_way["left_and_blocked_within_zone_frames"] == left["left_and_blocked_within_zone_frames"]
    negatives = []
    source = context()
    source.pop("portal_geometry_sha256")
    negatives.append(reject("missing_portal_source", source, trace(), "Missing source hash"))
    source = context()
    source["structure_kind"] = "intersection"
    negatives.append(reject("wrong_structure", source, trace(), "Tunnel identity"))
    source = context()
    source["one_way_native_survey"] = None
    negatives.append(reject("missing_direction_survey", source, trace(), "One-way"))
    negatives.append(reject("short_capture", context(), trace()[:-1], "Incomplete 30-second"))
    rows = trace()
    rows[210]["source_cameras"].pop("portal_side")
    negatives.append(reject("missing_camera", context(), rows, "Four source camera"))
    rows = trace()
    rows[210]["native_frame"] = rows[209]["native_frame"]
    negatives.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace()
    rows[210]["incoming_lane_sight_ray"] = {"status": "blocked", "clear_lower_bound_m": 18,
                                              "blocker_upper_bound_m": None}
    negatives.append(reject("missing_blocker_bracket", context(), rows, "blocker bracket"))
    rows = trace()
    rows[210]["body_xy_m"] = None
    negatives.append(reject("missing_body_footprint", context(), rows, "Full vehicle body"))
    proof = {"format": "worker-cpu-tunnel-approach-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"right": right, "left": left, "one_way_exception_context": one_way},
             "negative": negatives,
             "interpretation": "One-way status is preserved as exception context; no legal verdict inferred"}
    path = Path(__file__).with_name("tunnel-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negatives),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
