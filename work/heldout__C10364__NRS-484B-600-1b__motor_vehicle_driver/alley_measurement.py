"""Original-frame alley exposure measurements; no legal endangerment verdict."""

from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path

from shapely.geometry import Polygon


def _polygon(corners, name):
    if not isinstance(corners, list) or len(corners) != 4:
        raise ValueError(f"Missing four measured {name} footprint corners")
    try:
        points = [(float(x), float(y)) for x, y in corners]
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {name} footprint coordinates") from error
    if any(not isfinite(value) for point in points for value in point):
        raise ValueError(f"Nonfinite {name} footprint coordinates")
    polygon = Polygon(points)
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError(f"Invalid {name} footprint geometry")
    return polygon


def _read_jsonl(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing required original source: " + path.name)
    data = path.read_bytes()
    if not data:
        raise ValueError("Empty required original source: " + path.name)
    try:
        rows = [json.loads(line) for line in data.splitlines()]
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("Invalid original JSONL: " + path.name) from error
    return rows, sha256(data).hexdigest()


def measure(attempt):
    """Join three retained sources by Native frame and measure per-frame gaps.

    `participant_footprints.jsonl` retains ego, stationary pedestrian and owned
    property corners. `trace.jsonl` and `video_frames.jsonl` are original frame
    identities. Fixture-only derived channels are deliberately ignored.
    """
    root = Path(attempt)
    footprints, footprint_hash = _read_jsonl(root / "participant_footprints.jsonl")
    motion, motion_hash = _read_jsonl(root / "ego_motion.jsonl")
    trace, trace_hash = _read_jsonl(root / "trace.jsonl")
    frame_map, map_hash = _read_jsonl(root / "video_frames.jsonl")
    if (not footprints or len(footprints) != len(motion)
            or len(footprints) != len(trace) or len(trace) != len(frame_map)):
        raise ValueError("Original footprint, motion, trace and frame-map counts differ")
    identities = None
    previous = None
    observations = []
    for index, (footprint, velocity, state, video) in enumerate(zip(footprints, motion, trace, frame_map)):
        frame, time_s = footprint.get("frame"), footprint.get("time_s")
        if (type(frame) is not int or not isinstance(time_s, (int, float))
                or not isfinite(time_s) or velocity.get("frame") != frame
                or velocity.get("time_s") != time_s or state.get("frame") != frame
                or state.get("time_s") != time_s or video.get("carla_frame") != frame
                or video.get("time_s") != time_s or video.get("video_frame") != index
                or (previous is not None and (frame != previous[0] + 1 or time_s <= previous[1]))):
            raise ValueError("Original alley source/frame-map join failed")
        ids = tuple(footprint.get(name) for name in ("ego_id", "pedestrian_id", "property_id"))
        if any(value is None for value in ids) or len(set(ids)) != 3 or (identities and ids != identities):
            raise ValueError("Alley participant identity missing or changed")
        if velocity.get("ego_id") != ids[0]:
            raise ValueError("Alley motion participant identity changed")
        ego = _polygon(footprint.get("ego_corners"), "ego")
        person = _polygon(footprint.get("pedestrian_corners"), "pedestrian")
        prop = _polygon(footprint.get("property_corners"), "property")
        center = (ego.centroid.x, ego.centroid.y)
        speed = None if previous is None else hypot(center[0] - previous[2][0], center[1] - previous[2][1]) / (time_s - previous[1])
        try:
            vx, vy = (float(value) for value in velocity["velocity_xy"])
            ax, ay = (float(value) for value in velocity["acceleration_xy"])
            fx, fy = (float(value) for value in velocity["forward_xy"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Missing original ego motion readback") from error
        norm = hypot(fx, fy)
        if not all(isfinite(value) for value in (vx, vy, ax, ay, fx, fy)) or norm < 1e-9:
            raise ValueError("Invalid original ego motion readback")
        fx, fy = fx / norm, fy / norm
        forward_speed = max(0.0, vx * fx + vy * fy)
        braking_deceleration = max(0.0, -(ax * fx + ay * fy))
        stop_distance = (forward_speed ** 2 / (2 * braking_deceleration)
                         if braking_deceleration > 1e-6 else None)

        def conflict_proxy(target):
            longitudinal = ((target.centroid.x - ego.centroid.x) * fx
                            + (target.centroid.y - ego.centroid.y) * fy)
            return longitudinal / forward_speed if longitudinal > 0 and forward_speed > 1e-6 else None

        person_gap = ego.distance(person)
        property_gap = ego.distance(prop)
        observations.append({"frame": frame, "time_s": time_s, "ego_speed_mps": speed,
                             "ego_native_speed_mps": hypot(vx, vy),
                             "observed_braking_deceleration_mps2": braking_deceleration,
                             "braking_distance_proxy_m": stop_distance,
                             "pedestrian_time_to_station_proxy_s": conflict_proxy(person),
                             "property_time_to_station_proxy_s": conflict_proxy(prop),
                             "pedestrian_surface_gap_m": person_gap,
                             "property_surface_gap_m": property_gap,
                             "pedestrian_contact": person_gap == 0,
                             "property_contact": property_gap == 0})
        identities = ids
        previous = (frame, time_s, center)
    return {"frame_count": len(observations), "observations": observations,
            "minimum_pedestrian_gap_m": min(row["pedestrian_surface_gap_m"] for row in observations),
            "minimum_property_gap_m": min(row["property_surface_gap_m"] for row in observations),
            "maximum_observed_speed_mps": max((row["ego_speed_mps"] or 0) for row in observations),
            "source_sha256": {"participant_footprints.jsonl": footprint_hash,
                              "ego_motion.jsonl": motion_hash,
                              "trace.jsonl": trace_hash, "video_frames.jsonl": map_hash},
            "limitations": ["Speed is a finite-difference footprint-centre measurement.",
                            "Time to station is a forward-projection proxy, not a predicted collision.",
                            "Braking distance uses instantaneous measured deceleration and is unknown without braking.",
                            "No measured gap or speed defines statutory endangerment."]}
