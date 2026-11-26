"""Independent frame join for the basic speed rule's named conditions.

This measures sources. It deliberately returns no reasonable-speed verdict.
"""
from __future__ import annotations

from math import isfinite, sqrt

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
REQUIRED_WEATHER = ("precipitation", "fog_density", "sun_altitude_angle")


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not isfinite(value):
        raise ValueError("Missing finite source: " + name)
    return float(value)


def measure(frames, *, source_kind, rate_hz=20):
    if source_kind not in ("original_native", "synthetic_cpu_fixture"):
        raise ValueError("Unknown source kind")
    if rate_hz != 20 or len(frames) != 600:
        raise ValueError("Exact 30-second, 20-Hz source required")
    output = []
    previous_native = None
    first_time = None
    for index, row in enumerate(frames):
        if row.get("video_frame") != index:
            raise ValueError("Nonconsecutive video frame")
        native = row.get("native_frame")
        if not isinstance(native, int) or (previous_native is not None and native <= previous_native):
            raise ValueError("Native frame order changed")
        previous_native = native
        time_s = number(row.get("time_s"), "time_s")
        if first_time is None:
            first_time = time_s
        if abs(time_s - first_time - index / rate_hz) > 1e-4:
            raise ValueError("Contemporaneous Native time join changed")
        views = row.get("camera_frames")
        if not isinstance(views, dict) or set(views) != set(VIEWS) or any(views[v] != native for v in VIEWS):
            raise ValueError("Four original camera frame joins required")
        velocity = row.get("ego_velocity_xyz_mps")
        if not isinstance(velocity, list) or len(velocity) != 3:
            raise ValueError("Original ego velocity vector required")
        speed = sqrt(sum(number(v, "ego velocity") ** 2 for v in velocity))
        traffic = row.get("traffic")
        if not isinstance(traffic, list) or not traffic:
            raise ValueError("Contemporaneous traffic required")
        ids = set()
        for actor in traffic:
            if not isinstance(actor, dict) or not actor.get("native_actor_id") or actor["native_actor_id"] in ids:
                raise ValueError("Distinct Native traffic identity required")
            ids.add(actor["native_actor_id"])
            vector = actor.get("velocity_xyz_mps")
            if not isinstance(vector, list) or len(vector) != 3:
                raise ValueError("Traffic velocity vector required")
            for component in vector:
                number(component, "traffic velocity")
            if not isinstance(actor.get("class_source"), str) or not actor["class_source"]:
                raise ValueError("Traffic class source required")
        road = row.get("road")
        if not isinstance(road, dict) or not road.get("native_map_sha256") or not road.get("surface_source"):
            raise ValueError("Original road and surface sources required")
        if number(road.get("lane_width_m"), "lane_width_m") <= 0:
            raise ValueError("Positive lane width required")
        number(road.get("surface_wetness"), "surface_wetness")
        number(road.get("curvature_inv_m"), "curvature_inv_m")
        weather = row.get("weather")
        if not isinstance(weather, dict) or not all(key in weather for key in REQUIRED_WEATHER):
            raise ValueError("Contemporaneous weather required")
        for key in REQUIRED_WEATHER:
            number(weather[key], key)
        if not isinstance(row.get("visibility_source"), str) or not row["visibility_source"]:
            raise ValueError("Visibility source required")
        output.append({"video_frame": index, "native_frame": native, "time_s": time_s,
                       "ego_speed_mps": speed, "traffic_count": len(traffic),
                       "lane_width_m": road["lane_width_m"], "curvature_inv_m": road["curvature_inv_m"],
                       "surface_wetness": road["surface_wetness"],
                       "weather": weather})
    return {"format": "basic-speed-condition-source-v2", "source_kind": source_kind,
            "frame_count": len(output), "rate_hz": rate_hz,
            "ego_speed_mps": {"min": min(x["ego_speed_mps"] for x in output),
                              "max": max(x["ego_speed_mps"] for x in output),
                              "mean": sum(x["ego_speed_mps"] for x in output) / len(output)},
            "frame_measurements": output,
            "legal_judgment": "unresolved", "physical_acceptance": False}
