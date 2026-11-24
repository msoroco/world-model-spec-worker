"""Acquire original Native intersection packets for the exact 450(1)(c) cases.

The caller supplies a reviewed map-boundary packet, a case-specific controller,
and an independent activity observer. This module records what Native returned;
it never derives an exception or a legal result from the requested case name.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from intersection_observables import SourceError, _require


def _write(path: Path, value: dict) -> str:
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def body_footprint(actor) -> list[list[float]]:
    """Project Native's actual vehicle bounding box to a world XY polygon."""
    transform = actor.get_transform()
    box = actor.bounding_box
    _require(box.extent.x > 0 and box.extent.y > 0, "invalid Native body extent")
    angle = math.radians(transform.rotation.yaw)
    c, s = math.cos(angle), math.sin(angle)
    points = []
    for dx, dy in ((-box.extent.x, -box.extent.y), (box.extent.x, -box.extent.y),
                   (box.extent.x, box.extent.y), (-box.extent.x, box.extent.y)):
        x, y = box.location.x + dx, box.location.y + dy
        points.append([transform.location.x + c*x - s*y,
                       transform.location.y + s*x + c*y])
    _require(all(math.isfinite(v) for point in points for v in point), "nonfinite Native body")
    return points


def acquire(world, actor, boundary: dict, controller, observer, case_id: str,
            run_id: str, output: Path, sample_count: int = 900, media_writer=None) -> dict:
    """Tick a synchronous 20 Hz world and seal original packets for the finalizer.

    controller.step(frame_index, actor) requests behavior. observer.observe takes
    the Native snapshot and actor, and must return original activity/context
    observations with a source_ref. None or an absent field means unknown, not
    an absent exception. Supply NativeMediaWriter for the four-camera capture.
    """
    _require(case_id and run_id, "case and run identity required")
    _require(sample_count >= 2, "at least two original frames required")
    _require(world.get_map().name == boundary.get("map_id"), "Native map identity differs")
    _require(boundary.get("highway_status") == "reviewed_highway" and
             boundary.get("joining_roadways") is True and
             boundary.get("intersection_polygon") and boundary.get("source_refs"),
             "reviewed intersection boundary source missing")
    settings = world.get_settings()
    _require(settings.synchronous_mode and settings.fixed_delta_seconds == 0.05,
             "Native world must be synchronous at 20 Hz")
    output.mkdir(parents=True, exist_ok=True)
    samples, activities = [], []
    previous_frame, previous_time = None, None
    try:
        for index in range(sample_count):
            requested = controller.step(index, actor)
            _require(isinstance(requested, dict) and requested.get("source") == "original_controller_request",
                     "controller request source missing")
            world.tick()
            snapshot = world.get_snapshot()
            frame = snapshot.frame
            time_s = snapshot.timestamp.elapsed_seconds
            _require(isinstance(frame, int) and isinstance(time_s, (int, float)) and math.isfinite(time_s),
                     "invalid Native frame or time")
            if previous_frame is not None:
                _require(frame == previous_frame + 1 and abs((time_s - previous_time) - 0.05) < 1e-4,
                         "Native frame or 20 Hz time gap")
            previous_frame, previous_time = frame, time_s
            velocity = actor.get_velocity()
            speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
            _require(math.isfinite(speed), "nonfinite Native velocity")
            observed = observer.observe(snapshot, actor)
            _require(isinstance(observed, dict) and observed.get("source_ref") and
                     observed.get("activity_observation") is not None and
                     all(key in observed for key in ("traffic_conflict_observation",
                                                  "law_direction_observation",
                                                  "officer_direction_observation",
                                                  "device_direction_observation")),
                     "independent original activity/context observation missing")
            if media_writer is not None:
                media_writer.capture(snapshot, actor)
            samples.append({"frame": frame, "time_s": time_s,
                            "body_footprint": body_footprint(actor), "speed_mps": speed,
                            "controller_request": requested})
            activities.append({"frame": frame, **observed})
    except BaseException:
        if media_writer is not None:
            media_writer.abort()
        raise
    finally:
        controller.stop(actor)
    activity = {"case_id": case_id, "native_run_id": run_id,
                "activity_source": "original_native_activity_observer",
                "activity_samples": activities,
                "source_refs": [{"path": "activity.json", "native_run_id": run_id}],
                "activity_observation": activities[-1]["activity_observation"],
                "traffic_conflict_observation": activities[-1]["traffic_conflict_observation"],
                "law_direction_observation": activities[-1]["law_direction_observation"],
                "officer_direction_observation": activities[-1]["officer_direction_observation"],
                "device_direction_observation": activities[-1]["device_direction_observation"]}
    trace = {"case_id": case_id, "native_run_id": run_id,
             "map_id": boundary["map_id"], "fps": 20, "samples": samples,
             "source_refs": [{"path": "trace.json", "native_run_id": run_id}]}
    seals = {"boundary": _write(output / "boundary.json", boundary),
             "trace": _write(output / "trace.json", trace),
             "activity": _write(output / "activity.json", activity)}
    manifest = {"case_id": case_id, "native_run_id": run_id,
                **{key: {"path": key + ".json", "sha256": value}
                   for key, value in seals.items()}}
    if media_writer is not None:
        media_sha = media_writer.close(case_id=case_id, run_id=run_id,
                                       expected_frames=[row["frame"] for row in samples])
        manifest["media"] = {"path": "media-manifest.json", "sha256": media_sha}
    _write(output / "source-manifest.json", manifest)
    return {"case_id": case_id, "native_run_id": run_id,
            "frame_count": len(samples), "first_frame": samples[0]["frame"],
            "last_frame": samples[-1]["frame"], "source_seals": seals,
            "media_manifest_sha256": manifest.get("media", {}).get("sha256"),
            "physical_acceptance_claimed": False}
