"""Native acquisition request for the controlled diagonal device pair.

Coordinates and device phases are authored requests. Readback and an official
device survey are required before any physical or legal finding.
"""
from __future__ import annotations

import math

FRAMES = 600
RATE_HZ = 20
START_FRAME = 100
END_FRAME = 340
START = (-6.0, -6.0)
FINISH = (6.0, 6.0)
CAMERAS = (
    ("overview", 1920, 1080, (0.0, 0.0, 24.0), (-90.0, 0.0, 0.0)),
    ("approach", 1280, 720, (-12.0, -12.0, 5.0), (-18.0, 45.0, 0.0)),
    ("reference_corner", 1280, 720, (8.0, -8.0, 5.0), (-17.0, 135.0, 0.0)),
    ("device_face", 1280, 720, (-8.0, -8.0, 3.0), (-10.0, 45.0, 0.0)),
)


def request(case: str, frame: int) -> dict:
    if case not in ("controlled_1", "controlled_2") or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("unknown case or invalid Native frame")
    progress = max(0.0, min(1.0, (frame - START_FRAME) / (END_FRAME - START_FRAME)))
    position = [START[k] + progress * (FINISH[k] - START[k]) for k in (0, 1)]
    distance = math.dist(START, FINISH)
    direction = [(FINISH[k] - START[k]) / distance for k in (0, 1)] + [0.0]
    state = "diagonal_dont_walk" if case == "controlled_2" and START_FRAME <= frame < 160 else "diagonal_walk"
    return {
        "case": case, "frame": frame, "time_s": frame / RATE_HZ,
        "target_xy_m": position, "walker_direction_xyz": direction,
        "walker_speed_mps": distance * RATE_HZ / (END_FRAME - START_FRAME) if START_FRAME <= frame < END_FRAME else 0.0,
        "device_id": "c109166-diagonal-crossing-head", "device_display_request": state,
        "official_status_verified": False, "diagonal_authorization_verified": False,
        "native_pose_observed": False, "source_kind": "authored_native_request",
    }


def apply_walker_control(walker, carla, case: str, frame: int) -> dict:
    row = request(case, frame)
    walker.apply_control(carla.WalkerControl(carla.Vector3D(*row["walker_direction_xyz"]),
                                          row["walker_speed_mps"], False))
    return row


def camera_plan() -> list[dict]:
    return [{"name": name, "width": width, "height": height, "fps": RATE_HZ,
             "location_xyz_m": list(location), "rotation_pitch_yaw_roll_deg": list(rotation),
             "source_required": True}
            for name, width, height, location, rotation in CAMERAS]


def install_cameras(world, carla, on_frame):
    actors = []
    try:
        for item in camera_plan():
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(item["width"]))
            blueprint.set_attribute("image_size_y", str(item["height"]))
            blueprint.set_attribute("sensor_tick", "0.05")
            sensor = world.spawn_actor(blueprint, carla.Transform(
                carla.Location(*item["location_xyz_m"]),
                carla.Rotation(*item["rotation_pitch_yaw_roll_deg"])))
            if sensor is None:
                raise ValueError("camera spawn failed: " + item["name"])
            sensor.listen(lambda image, name=item["name"]: on_frame(name, image))
            actors.append((item["name"], sensor))
        return actors
    except Exception:
        for _, sensor in reversed(actors):
            sensor.stop()
            sensor.destroy()
        raise


def validate_source_frames(rows: list[dict]) -> dict:
    expected = {item["name"]: item for item in camera_plan()}
    if len(rows) != FRAMES * len(expected):
        raise ValueError("four complete source-camera streams required")
    seen = set()
    for row in rows:
        name, frame = row.get("camera"), row.get("frame")
        if name not in expected or type(frame) is not int or not 0 <= frame < FRAMES:
            raise ValueError("invalid camera/frame identity")
        key = name, frame
        if key in seen:
            raise ValueError("duplicate source-camera frame")
        seen.add(key)
        if (row.get("native_frame") != frame or row.get("time_s") != frame / RATE_HZ or
                row.get("width") != expected[name]["width"] or
                row.get("height") != expected[name]["height"] or
                not row.get("source_path") or not row.get("source_sha256")):
            raise ValueError("source-camera frame join or source missing")
    if seen != {(name, frame) for name in expected for frame in range(FRAMES)}:
        raise ValueError("missing source-camera frame")
    return {"frames_per_camera": FRAMES, "source_camera_frames": len(seen),
            "camera_names": sorted(expected), "actual_pixels_reviewed": False}


def validate_pair() -> dict:
    changed = []
    for frame in range(FRAMES):
        first, second = request("controlled_1", frame), request("controlled_2", frame)
        for key in first:
            if key not in ("case", "device_display_request") and first[key] != second[key]:
                raise ValueError("controlled Native request changes " + key)
        if first["device_display_request"] != second["device_display_request"]:
            changed.append(frame)
    if changed != list(range(START_FRAME, 160)):
        raise ValueError("first-entry device contrast changed")
    return {"frames": FRAMES, "rate_hz": RATE_HZ, "duration_s": FRAMES / RATE_HZ,
            "changed_device_frames": [changed[0], changed[-1]],
            "changed_device_frame_count": len(changed), "walker_requests_identical": True,
            "camera_names": [item["name"] for item in camera_plan()],
            "official_device_verified": False, "physical_completion_claimed": False}
