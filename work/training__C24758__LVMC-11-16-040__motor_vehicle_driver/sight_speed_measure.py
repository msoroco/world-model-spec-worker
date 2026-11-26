"""Source-bound diagnostic for the LVMC 11.16.040 selected sight branch.

The output describes measured inputs, not prima facie status or legal compliance.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

FEET_TO_M = 0.3048
APPROACH_M = 100 * FEET_TO_M
MPS_TO_MPH = 2.2369362921
EXPECTED_ID = "training__C24758__LVMC-11-16-040__motor_vehicle_driver"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite_number(value, name):
    require(isinstance(value, (float, int)) and not isinstance(value, bool)
            and math.isfinite(value), f"invalid {name}")
    return float(value)


def measure(source_path, expected_sha256):
    raw = Path(source_path).read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    require(actual_sha == expected_sha256, "source sha256 mismatch")
    source = json.loads(raw)
    require(source.get("assignment_id") == EXPECTED_ID, "assignment mismatch")
    require(source.get("source_kind") == "native_saved_observation", "unsealed source kind")
    require(source.get("frame_rate_hz") == 20, "frame rate mismatch")
    approaches = source.get("entering_approach_ids")
    require(isinstance(approaches, list) and len(approaches) >= 2
            and len(approaches) == len(set(approaches))
            and all(isinstance(a, str) and a for a in approaches),
            "entering approach inventory missing")
    context = source.get("context", {})
    for name in ("through_street", "traffic_controlled_intersection"):
        item = context.get(name, {})
        require(item.get("value") is False and isinstance(item.get("source_ref"), str)
                and item["source_ref"], f"unresolved exception: {name}")
    frames = source.get("frames")
    require(isinstance(frames, list) and len(frames) >= 600, "incomplete 30-second trace")
    prior_distance = float("inf")
    prior_time = -1.0
    approach_frames = []
    traversal_speeds = []
    for i, frame in enumerate(frames):
        require(frame.get("frame") == i, "nonconsecutive frame identity")
        time = finite_number(frame.get("time_s"), "time_s")
        require(abs(time - i / 20) < 0.0001 and time > prior_time,
                "frame/time join mismatch")
        prior_time = time
        distance = finite_number(frame.get("distance_to_boundary_m"),
                                 "distance_to_boundary_m")
        speed = finite_number(frame.get("ego_speed_mps"), "ego_speed_mps")
        require(speed >= 0, "negative ego speed")
        require(distance <= prior_distance + 0.05, "approach distance reverses")
        prior_distance = distance
        if 0 <= distance <= APPROACH_M:
            require(type(frame.get("intersection_clear_100ft")) is bool,
                    "intersection view missing")
            views = frame.get("entering_approach_views")
            require(isinstance(views, dict) and set(views) == set(approaches),
                    "entering approach view inventory mismatch")
            for approach_id, view in views.items():
                require(type(view.get("clear_100ft")) is bool
                        and type(view.get("traffic_visible_100ft")) is bool
                        and isinstance(view.get("source_ref"), str)
                        and view["source_ref"],
                        f"view source missing: {approach_id}")
            approach_frames.append({"frame": i, "distance_to_boundary_m": distance,
                                    "intersection_clear": frame["intersection_clear_100ft"],
                                    "all_entering_clear": all(v["clear_100ft"] for v in views.values()),
                                    "all_traffic_visible": all(v["traffic_visible_100ft"] for v in views.values())})
        if frame.get("within_intersection") is True:
            traversal_speeds.append(speed * MPS_TO_MPH)
        else:
            require(frame.get("within_intersection") is False,
                    "intersection traversal flag missing")
    require(approach_frames, "last 100 feet not sampled")
    require(max(x["distance_to_boundary_m"] for x in approach_frames) >= APPROACH_M - 1.0,
            "last 100 feet not covered")
    require(min(x["distance_to_boundary_m"] for x in approach_frames) <= 0.5,
            "intersection boundary not reached")
    require(traversal_speeds, "intersection traversal absent")
    sight_limited = [x["frame"] for x in approach_frames
                     if not (x["intersection_clear"] and x["all_entering_clear"]
                             and x["all_traffic_visible"])]
    return {"format": "worker-sight-speed-diagnostic-v1",
            "assignment_id": EXPECTED_ID, "source_path": str(source_path),
            "source_sha256": actual_sha, "frame_count": len(frames),
            "entering_approach_ids": approaches,
            "exception_context_source_refs": {k: context[k]["source_ref"] for k in
                                               ("through_street", "traffic_controlled_intersection")},
            "last_100ft_sampled_frames": len(approach_frames),
            "sight_limited_frame_count": len(sight_limited),
            "sight_limited_first_frame": sight_limited[0] if sight_limited else None,
            "traversal_speed_mph_min": min(traversal_speeds),
            "traversal_speed_mph_max": max(traversal_speeds),
            "statutory_speed_reference_mph": 15,
            "legal_verdict": None,
            "limitation": "Boolean sight and exception inputs require independently reviewed Native provenance; temporal and legal interpretation is not decided here."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = measure(args.source, args.source_sha256)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
