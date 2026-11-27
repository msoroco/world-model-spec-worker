"""Source-bound descriptive measurements for NRS 484B.213(1).

The result contains physical observations and does not decide statutory judgment phrases.
Input is an original-index projection of sealed Native map, ray, and actor sources.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_ROLES = ("ego", "overtaken")


def _finite_number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"missing numeric {label}")
    value = float(value)
    if not -1e9 < value < 1e9:
        raise ValueError(f"invalid numeric {label}")
    return value


def measure(packet):
    if packet.get("format") != "nrs-484b-213-1-native-projection":
        raise ValueError("wrong source projection")
    source = packet.get("source") or {}
    if not source.get("native_result_sha256") or not source.get("map_sha256") or not source.get("frame_map_sha256"):
        raise ValueError("missing sealed Native source bindings")
    road = packet.get("road") or {}
    if road.get("public_highway") is not True or road.get("lane_count") != 2 or road.get("opposite_permitted_directions") is not True or road.get("undivided") is not True:
        raise ValueError("unqualified two-lane two-directional highway")
    if not road.get("centerline_source"):
        raise ValueError("missing centerline source")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 2:
        raise ValueError("missing original frame history")
    indices = [f.get("original_frame") for f in frames]
    if indices != list(range(indices[0], indices[0] + len(indices))) or indices[0] != 0:
        raise ValueError("incomplete original frame sequence")
    observed = []
    for frame in frames:
        actors = frame.get("actors") or {}
        for role in REQUIRED_ROLES:
            if role not in actors:
                raise ValueError(f"missing {role} original actor")
        ego, target = actors["ego"], actors["overtaken"]
        if ego.get("vehicle") is not True or target.get("vehicle") is not True:
            raise ValueError("unqualified vehicle actor")
        if ego.get("direction") != target.get("direction"):
            raise ValueError("overtaken vehicle not same-direction")
        if not frame.get("ray_source_sha256") or not isinstance(frame.get("left_side_rays"), list) or not frame["left_side_rays"]:
            raise ValueError("missing original left-side visibility rays")
        rays = frame["left_side_rays"]
        for ray in rays:
            _finite_number(ray.get("clear_distance_m"), "ray clear distance")
            if ray.get("censored") not in (True, False):
                raise ValueError("missing ray censoring")
            if not ray.get("hit_kind"):
                raise ValueError("missing ray hit classification")
        e_station = _finite_number(ego.get("station_m"), "ego station")
        t_station = _finite_number(target.get("station_m"), "overtaken station")
        e_lateral = _finite_number(ego.get("centerline_signed_body_edge_m"), "ego centerline side")
        e_rear = _finite_number(ego.get("rear_station_m"), "ego rear station")
        t_front = _finite_number(target.get("front_station_m"), "overtaken front station")
        e_speed = _finite_number(ego.get("speed_mps"), "ego speed")
        t_speed = _finite_number(target.get("speed_mps"), "overtaken speed")
        oncoming = actors.get("oncoming")
        separation = None
        response = None
        if oncoming is not None:
            if oncoming.get("vehicle") is not True or oncoming.get("direction") == ego.get("direction"):
                raise ValueError("oncoming actor direction or class invalid")
            separation = _finite_number(oncoming.get("station_m"), "oncoming station") - e_station
            response = {"speed_mps": _finite_number(oncoming.get("speed_mps"), "oncoming speed"),
                        "lateral_m": _finite_number(oncoming.get("lateral_m"), "oncoming lateral")}
        observed.append({"original_frame": frame["original_frame"], "ego_station_m": e_station,
                         "overtaken_station_m": t_station, "ego_left_of_center": e_lateral > 0,
                         "ego_fully_right_of_center": e_lateral <= 0,
                         "ego_rear_station_m": e_rear,
                         "overtaken_front_station_m": t_front,
                         "ego_speed_mps": e_speed, "overtaken_speed_mps": t_speed,
                         "oncoming_forward_station_gap_m": separation,
                         "oncoming_response": response,
                         "left_ray_clear_distance_min_m": min(r["clear_distance_m"] for r in rays),
                         "left_ray_any_occluded": any(r["hit_kind"] == "opaque_obstacle" for r in rays)})
    left_frames = [f["original_frame"] for f in observed if f["ego_left_of_center"]]
    if not left_frames:
        raise ValueError("no measured left-of-center episode")
    first_left = left_frames[0]
    passed = [f for f in observed if f["original_frame"] >= first_left and
              f["ego_rear_station_m"] > f["overtaken_front_station_m"] and
              f["ego_fully_right_of_center"]]
    return {"format": "nrs-484b-213-1-measurements", "source": source,
            "original_frame_count": len(observed), "left_of_center_frames": left_frames,
            "measured_pass_and_return_frame": passed[0]["original_frame"] if passed else None,
            "per_frame": observed,
            "judgments": {"clearly_visible": "unresolved", "sufficient_distance": "unresolved",
                          "interference_with_safe_operation": "unresolved"}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = measure(json.loads(args.source.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
