"""Acquire original crossing-stop motion and four synchronized camera sources.

Raw traces remain in a fresh .runtime-work attempt. Saved processing and legal
review happen after this module returns and all Native resources are closed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from native_control import step


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _finite(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("invalid original Native sample: " + label)
    return float(value)


def _motion(actor):
    transform = actor.get_transform()
    location = transform.location
    velocity = actor.get_velocity()
    extent = actor.bounding_box.extent
    return {"position_m": [_finite(getattr(location, axis), "position " + axis)
                           for axis in ("x", "y", "z")],
            "velocity_mps": [_finite(getattr(velocity, axis), "velocity " + axis)
                             for axis in ("x", "y", "z")],
            "heading_deg": _finite(transform.rotation.yaw, "heading"),
            "bbox_half_extent_m": [_finite(getattr(extent, axis), "bbox " + axis)
                                   for axis in ("x", "y", "z")],
            "actor_id": actor.id}


def capture(world, scene, camera_rig, attempt: Path, case_id: str,
            vehicle_control_factory, *, frame_map_factory=None, count: int = 900) -> dict:
    """Retain 900 frame-joined Native observations with live actor positions."""
    if count != 900:
        raise ValueError("exact crossing capture requires 900 frames")
    attempt = Path(attempt).resolve()
    if ".runtime-work" not in attempt.parts:
        raise ValueError("original Native output must stay under .runtime-work")
    if attempt.exists() and any(path.name != "raw" for path in attempt.iterdir()):
        raise ValueError("retain existing original Native attempt")
    settings = world.get_settings()
    if (settings.synchronous_mode is not True or settings.no_rendering_mode is not False or
            abs(_finite(settings.fixed_delta_seconds, "fixed step") - .05) > 1e-9):
        raise ValueError("rendered synchronous 20 Hz Native world required")
    if frame_map_factory is None:
        from worker_exchange.native_output import FrameMap
        frame_map_factory = FrameMap
    attempt.mkdir(parents=True, exist_ok=True)
    previous = None
    with frame_map_factory(attempt / "video_frames.jsonl") as mapping:
        with (attempt / "trace.jsonl").open("x", encoding="utf-8") as stream:
            for index in range(count):
                controls = step(scene, vehicle_control_factory)
                tick_frame = world.tick()
                snapshot = world.get_snapshot()
                frame = snapshot.frame
                time_s = _finite(snapshot.timestamp.elapsed_seconds, "snapshot time")
                if frame != tick_frame or (previous is not None and
                        (frame != previous[0] + 1 or
                         not .049 <= time_s - previous[1] <= .051)):
                    raise ValueError("original Native crossing frame cadence differs")
                previous = frame, time_s
                cameras = camera_rig.await_frame(frame, time_s)
                if not isinstance(cameras, dict) or set(cameras) != set(VIEWS):
                    raise ValueError("original four camera frame sources missing")
                for name in VIEWS:
                    image = cameras[name]
                    if (image.get("frame") != frame or
                            abs(_finite(image.get("time_s"), name + " time") - time_s) > .05 or
                            not image.get("sha256") or not image.get("raw_bgra")):
                        raise ValueError("original camera/Native frame join differs")
                ego = _motion(scene.ego)
                velocity = ego["velocity_mps"]
                row = {"case_id": case_id, "frame": frame, "source_frame": frame,
                       "time_s": time_s, "ego": ego,
                       "position": dict(zip(("x", "y", "z"), ego["position_m"])),
                       "position_m": ego["position_m"],
                       "heading_deg": ego["heading_deg"],
                       "speed_mps": math.dist(velocity, (0., 0., 0.)),
                       "speed_mph": math.dist(velocity, (0., 0., 0.)) / .44704,
                       "companion": _motion(scene.companion) if scene.companion else None,
                       "controls": controls,
                       "authored_marked_lane_count": len(scene.packet["marked_lanes"]),
                       "authored_stop_line_x_m": scene.packet["stop_line_x_m"],
                       "authored_rail_line_x_m": scene.packet["rail_line_x_m"],
                       "source_packet_sha256": scene.packet["source_packet_sha256"],
                       "camera_sources": cameras,
                       "physical_acceptance_claimed": False,
                       "legal_judgment": "unresolved"}
                stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                mapping.append(frame, time_s,
                               camera_source_sha256={name: cameras[name]["sha256"]
                                                     for name in VIEWS})
    return {"case_id": case_id, "frames": count,
            "first_frame": previous[0] - count + 1, "last_frame": previous[0],
            "trace_reference": "trace.jsonl",
            "video_frame_map_reference": "video_frames.jsonl",
            "physical_acceptance_claimed": False,
            "legal_judgment": "unresolved"}
