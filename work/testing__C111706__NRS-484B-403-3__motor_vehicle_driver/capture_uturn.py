"""Original 20 Hz two-vehicle acquisition for the assigned U-turn cases.

The caller owns world synchrony, actor construction, cameras and restoration.
No CARLA import occurs here; the supplied world and actors are read directly.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class CaptureError(ValueError):
    pass


def _need(ok: bool, message: str) -> None:
    if not ok:
        raise CaptureError(message)


def _seal(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _position(actor, road_map) -> dict:
    transform = actor.get_transform()
    loc = transform.location
    waypoint = road_map.get_waypoint(loc, project_to_road=False)
    _need(waypoint is not None, "original actor waypoint missing")
    corners = actor.bounding_box.get_world_vertices(transform)
    _need(len(corners) >= 4, "original body vertices missing")
    values = {
        "id": actor.id,
        "road_id": waypoint.road_id,
        "lane_id": waypoint.lane_id,
        "junction_id": waypoint.get_junction().id if waypoint.is_junction else None,
        "x": float(loc.x), "y": float(loc.y),
        "yaw_deg": float(transform.rotation.yaw),
        "body_corners_xy_m": [[float(vertex.x), float(vertex.y)] for vertex in corners],
    }
    _need(all(math.isfinite(v) for v in (values["x"], values["y"], values["yaw_deg"])),
          "nonfinite actor pose")
    _need(all(math.isfinite(v) for point in values["body_corners_xy_m"] for v in point),
          "nonfinite body vertex")
    return values


def capture(world, ego, other, site_path: Path, expected_site_sha256: str,
            expected_case: str, output: Path, ego_control, other_control, brake_control,
            *, ticks: int = 900, step_s: float = 0.05) -> dict:
    """Write a sealed projection only after all original ticks are acquired.

    Control callbacks receive (actor, tick_index) and must apply a control.
    The brake callback receives each actor and must apply full braking.
    They may implement an independently reviewed waypoint follower. A synthetic
    callback cannot establish physical completion. Camera capture is separate.
    """
    _need(_seal(site_path) == expected_site_sha256, "site source hash mismatch")
    site = json.loads(site_path.read_text(encoding="utf-8"))
    _need(site.get("case_id") == expected_case, "case identity mismatch")
    _need(site.get("map_sha256") and site.get("route_sha256"), "map/route source missing")
    _need(site.get("district_source_sha256"), "district source missing")
    boundary = site.get("intersection_boundary", {})
    _need(boundary.get("source_sha256") and len(boundary.get("polygon_xy_m", [])) >= 3,
          "intersection boundary source missing")
    _need(ticks == 900 and step_s == 0.05, "capture must be 900 ticks at 20 Hz")
    _need(ego.id != other.id, "participant identities collide")
    settings = world.get_settings()
    _need(settings.synchronous_mode and math.isclose(settings.fixed_delta_seconds, step_s,
          rel_tol=0, abs_tol=1e-9), "world must be synchronous at 20 Hz")
    road_map = world.get_map()
    _need(road_map.name == site.get("map_name"), "wrong live map")
    frames = []
    prior_frame = None
    prior_time = None
    try:
        for index in range(ticks):
            ego_control(ego, index)
            other_control(other, index)
            frame = world.tick()
            snapshot = world.get_snapshot()
            t = float(snapshot.timestamp.elapsed_seconds)
            _need(snapshot.frame == frame, "world tick/snapshot mismatch")
            if prior_frame is not None:
                _need(frame == prior_frame + 1, "noncontiguous original frame")
                _need(math.isclose(t - prior_time, step_s, rel_tol=0, abs_tol=1e-3),
                      "original tick interval mismatch")
            _need(math.isfinite(t), "nonfinite original time")
            frames.append({"frame": frame, "time_s": t,
                           "ego": _position(ego, road_map),
                           "other_vehicle": _position(other, road_map)})
            prior_frame, prior_time = frame, t
    finally:
        # A failed readback must not leave a vehicle under commanded throttle.
        for actor in (ego, other):
            brake_control(actor)
    packet = {
        "case_id": expected_case, "actor": "motor_vehicle_driver",
        "site_sha256": expected_site_sha256,
        "map_sha256": site["map_sha256"], "route_sha256": site["route_sha256"],
        "district_basis": {"source_sha256": site["district_source_sha256"]},
        "intersection_boundary": boundary,
        "ego_id": ego.id, "other_id": other.id,
        "frames": frames,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(packet, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(output)
    return {"path": str(output), "sha256": _seal(output), "frame_count": len(frames),
            "first_frame": frames[0]["frame"], "last_frame": frames[-1]["frame"]}
