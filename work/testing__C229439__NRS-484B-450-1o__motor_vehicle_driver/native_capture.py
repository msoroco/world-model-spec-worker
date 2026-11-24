"""Original 900-tick CARLA parking capture, requiring reviewed context per tick.

The context observer must independently report halt activity and each statutory
exception. Missing observations stop capture; controller intent is never reused
as evidence of actual behavior.
"""
from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path

from native_camera_writer import DIMENSIONS, NativeCameraWriter, seal_rows


POSES = {
    "front": ((1.5, 0.0, 1.7), (0.0, 0.0, 0.0)),
    "rear": ((-1.5, 0.0, 1.7), (0.0, 180.0, 0.0)),
    "left": ((0.0, -0.5, 1.7), (0.0, -90.0, 0.0)),
    "right": ((0.0, 0.5, 1.7), (0.0, 90.0, 0.0)),
}
CONTEXT_KEYS = ("traffic_conflict", "police_direction", "law_direction",
                "device_direction", "halt_activity")


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def make_cameras(world, api, ego, owned, reviewed_poses):
    """Spawn four RGB sensors only from independently reviewed camera poses."""
    _require(set(reviewed_poses) == set(POSES), "four reviewed camera poses required")
    cameras = {}
    for name, dimensions in DIMENSIONS.items():
        pose = reviewed_poses[name]
        _require(len(pose) == 2 and all(len(part) == 3 for part in pose),
                 "reviewed camera pose incomplete")
        bp = world.get_blueprint_library().find("sensor.camera.rgb")
        for key, value in (("image_size_x", dimensions[0]),
                           ("image_size_y", dimensions[1]), ("sensor_tick", 0.05)):
            bp.set_attribute(key, str(value))
        transform = api.Transform(api.Location(*pose[0]), api.Rotation(*pose[1]))
        sensor = world.try_spawn_actor(bp, transform, attach_to=ego)
        _require(sensor is not None and sensor.type_id == "sensor.camera.rgb",
                 "original RGB sensor spawn failed")
        owned.append(sensor)
        cameras[name] = sensor
    return cameras


def original_row(snapshot, ego, case, device, site, context, pixel_bindings):
    _require(set(CONTEXT_KEYS) <= set(context), "independent per-frame context missing")
    for key in CONTEXT_KEYS[:-1]:
        _require(type(context[key]) is bool, "exception observation must be boolean")
    _require(context["halt_activity"] in {"stop", "stand", "park", "travel"},
             "observed halt activity missing")
    vertices = ego.bounding_box.get_world_vertices(ego.get_transform())
    _require(len(vertices) == 8, "original body vertices missing")
    speed = float(ego.get_velocity().length())
    _require(math.isfinite(speed) and speed >= 0, "original speed invalid")
    x_values = [float(v.x) for v in vertices]
    y_values = [float(v.y) for v in vertices]
    footprint = [[min(x_values), min(y_values)], [max(x_values), min(y_values)],
                 [max(x_values), max(y_values)], [min(x_values), max(y_values)]]
    return {"frame": snapshot.frame, "time_s": float(snapshot.timestamp.elapsed_seconds),
            "case_id": case["case_id"], "subject_id": str(ego.id),
            "device_id": device["device_id"], "device_instruction": device["exact_instruction"],
            "device_effective": bool(context["device_effective"]),
            "prohibited_actions": list(device["prohibited_actions"]),
            "halt_activity": context["halt_activity"],
            "traffic_conflict": context["traffic_conflict"],
            "police_direction": context["police_direction"],
            "law_direction": context["law_direction"],
            "device_direction": context["device_direction"],
            "speed_mps": speed,
            "body_corners_xy": footprint,
            "camera_frames": pixel_bindings}


def capture(world, api, adapter, case, site, device, context_observer,
            output_dir, reviewed_camera_poses, *, camera_writer_factory=NativeCameraWriter):
    """Run exactly 900 original world ticks and seal one saved attempt."""
    _require(adapter.ego is not None and adapter.device is not None,
             "reviewed Native scene not constructed")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    sensors = make_cameras(world, api, adapter.ego, adapter.owned, reviewed_camera_poses)
    writer = camera_writer_factory(sensors, root)
    rows = []
    first_frame = None
    for index in range(900):
        adapter.control_step()
        tick_frame = world.tick()
        snapshot = world.get_snapshot()
        _require(snapshot.frame == tick_frame, "original world tick readback differs")
        if first_frame is None:
            first_frame = tick_frame
        _require(tick_frame == first_frame + index,
                 "original world tick sequence differs")
        observed = context_observer(snapshot, adapter.ego, device)
        _require(type(observed.get("device_effective")) is bool,
                 "original device effective readback missing")
        pixels = writer.capture(snapshot)
        rows.append(original_row(snapshot, adapter.ego, case, device, site, observed, pixels))
    camera_refs = writer.close()
    refs = seal_rows(root, rows, camera_refs)
    source_context = {'actor_rows.json': refs['actor_rows']}
    for name, value in (('site-source.json', site), ('device-source.json', device)):
        path = root / name
        path.write_text(json.dumps(value, indent=2) + '\n')
        source_context[name] = {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    attempt = {"source_format": "native_original", "case_id": case["case_id"],
               "subject_id": str(adapter.ego.id), "device_id": device["device_id"],
               "device_instruction": device["exact_instruction"],
               "parking_polygon": site["parking_polygon"], "halt_action": case["halt_action"],
               "frame_count": 900, "first_frame": first_frame, "fps": 20,
               "source_context": source_context, **refs}
    (root / "attempt.json").write_text(json.dumps(attempt, indent=2) + "\n")
    return attempt
