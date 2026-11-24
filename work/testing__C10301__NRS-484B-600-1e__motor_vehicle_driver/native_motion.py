"""Lazy Native speed acquisition for the three exact boundary probes.

The caller supplies a reviewed route and camera capture. This module only
controls and reads the ego actor; CPU tests use a fake world and actor.
"""

from __future__ import annotations

import json
import math
import hashlib
from pathlib import Path

from speed_capture import write_original_speed
from delivery_audit import CAMERAS

FRAMES = 900
HZ = 20
MPH_PER_MPS = 2.2369362920544
TARGETS = {"below": 75.0, "equal": 80.0, "above": 85.0}
CASE_PREFIX = "testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__"


def _speed(actor) -> float:
    velocity = actor.get_velocity()
    components = (velocity.x, velocity.y, velocity.z)
    if any(type(value) not in (int, float) or not math.isfinite(value)
           for value in components):
        raise ValueError("invalid original Native velocity")
    return math.sqrt(sum(value * value for value in components))


def _position(actor) -> tuple[float, float, float]:
    location = actor.get_transform().location
    components = (location.x, location.y, location.z)
    if any(type(value) not in (int, float) or not math.isfinite(value)
           for value in components):
        raise ValueError("invalid original Native position")
    return tuple(float(value) for value in components)


def capture_speed(world, actor, control_factory, attempt: Path, case_id: str,
                  native_run_id: str, uncertainty_mps: float, *,
                  diagnostic_fixture: bool = False,
                  camera_frame_reader=None, route_reader=None) -> dict:
    """Tick at 20 Hz, retain original speeds, and stop the actor on every exit.

    ``uncertainty_mps`` is supplied by the reviewed acquisition plan. It is not
    inferred from a requested speed or a synthetic fixture.
    """
    suffix = case_id.rsplit("__", 1)[-1]
    if suffix not in TARGETS or case_id != CASE_PREFIX + suffix:
        raise ValueError("unknown exact boundary case")
    if (type(uncertainty_mps) not in (int, float) or
            not math.isfinite(uncertainty_mps) or uncertainty_mps < 0):
        raise ValueError("invalid reviewed speed uncertainty")
    if type(diagnostic_fixture) is not bool:
        raise ValueError("invalid diagnostic fixture flag")
    attempt = Path(attempt)
    reserved = ["original-speed.jsonl", "speed-source.json",
                "native-motion-receipt.json"]
    if camera_frame_reader is not None:
        reserved.append("camera-frame-readback.json")
    if route_reader is not None:
        reserved.append("route-frame-readback.json")
    if any((attempt / name).exists() for name in reserved):
        raise ValueError("original Native attempt artifact already exists")
    settings = world.get_settings()
    if not settings.synchronous_mode or abs(settings.fixed_delta_seconds - 1 / HZ) > 1e-9:
        raise ValueError("Native world must tick synchronously at 20 Hz")
    target = TARGETS[suffix] / MPH_PER_MPS
    rows = []
    camera_rows = []
    route_rows = []
    first_elapsed = None
    first_position = None
    previous_frame = None
    try:
        for index in range(FRAMES):
            observed = _speed(actor)
            error = target - observed
            throttle = min(1.0, max(0.0, 0.20 + 0.12 * error)) if error > 0 else 0.0
            brake = min(1.0, max(0.0, -0.12 * error)) if error < 0 else 0.0
            actor.apply_control(control_factory(throttle=throttle, brake=brake))
            frame = world.tick()
            snapshot = world.get_snapshot()
            if (type(frame) is not int or type(snapshot.frame) is not int or
                    frame != snapshot.frame or
                    (previous_frame is not None and frame != previous_frame + 1)):
                raise ValueError("Native frame identity or sequence differs")
            elapsed = snapshot.timestamp.elapsed_seconds
            if type(elapsed) not in (int, float) or not math.isfinite(elapsed):
                raise ValueError("invalid Native elapsed time")
            if first_elapsed is None:
                first_elapsed = elapsed
                first_position = _position(actor)
            if abs((elapsed - first_elapsed) - index / HZ) > 1e-5:
                raise ValueError("Native 20 Hz clock differs")
            rows.append({"frame": frame, "time_s": index / HZ,
                         "speed_mps": _speed(actor),
                         "speed_uncertainty_mps": float(uncertainty_mps)})
            if route_reader is not None:
                route = route_reader(actor)
                if (not isinstance(route, dict) or
                        route.get('source') != 'original_native_route_readback' or
                        type(route.get('road_id')) is not int or
                        type(route.get('lane_id')) is not int or
                        type(route.get('route_s_m')) not in (int, float) or
                        type(route.get('centerline_offset_m')) not in (int, float) or
                        not math.isfinite(route['route_s_m']) or
                        not math.isfinite(route['centerline_offset_m']) or
                        route['centerline_offset_m'] < 0 or
                        route['centerline_offset_m'] > 2.0):
                    raise ValueError('original Native route readback invalid')
                route_rows.append({'frame': frame, **route})
            if camera_frame_reader is not None:
                camera_frames = camera_frame_reader(frame)
                if (not isinstance(camera_frames, dict) or
                        camera_frames != {camera: frame for camera in CAMERAS}):
                    raise ValueError("original four-camera frame readback differs")
                camera_rows.append({"frame": frame,
                                    "camera_frames": camera_frames})
            previous_frame = frame
        travel_m = math.dist(first_position, _position(actor))
        if travel_m < 100:
            raise ValueError("Native ego did not travel the reviewed route")
        descriptor = write_original_speed(attempt, case_id, native_run_id, rows,
                                          diagnostic_fixture=diagnostic_fixture)
        camera_hash = None
        if camera_frame_reader is not None:
            camera_bytes = (json.dumps({"case_id": case_id,
                                         "native_run_id": native_run_id,
                                         "frames": camera_rows},
                                        sort_keys=True, separators=(",", ":")) + "\n").encode()
            camera_path = attempt / "camera-frame-readback.json"
            camera_path.write_bytes(camera_bytes)
            camera_hash = hashlib.sha256(camera_bytes).hexdigest()
        route_hash = None
        if route_reader is not None:
            route_bytes = (json.dumps({'case_id': case_id,
                                       'native_run_id': native_run_id,
                                       'frames': route_rows},
                                      sort_keys=True, separators=(',', ':')) + '\n').encode()
            (attempt / 'route-frame-readback.json').write_bytes(route_bytes)
            route_hash = hashlib.sha256(route_bytes).hexdigest()
        receipt = {"format": "c10301-native-motion-v1", "case_id": case_id,
                   "native_run_id": native_run_id, "sample_count": FRAMES,
                   "travel_m": travel_m, "speed_source_sha256": descriptor["sha256"],
                   "diagnostic_fixture": diagnostic_fixture,
                   "physical_acceptance_claimed": False}
        if camera_hash is not None:
            receipt["camera_frame_readback_sha256"] = camera_hash
        if route_hash is not None:
            receipt['route_frame_readback_sha256'] = route_hash
        (attempt / "native-motion-receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return receipt
    finally:
        actor.apply_control(control_factory(throttle=0.0, brake=1.0))
