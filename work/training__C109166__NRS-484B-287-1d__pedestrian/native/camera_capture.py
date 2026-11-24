"""Four source-camera acquisition for the C109166 diagonal request.

The local Native run must replace authored camera poses after map survey and
verify device pixels. This module only installs sensors and checks frame joins.
"""
from __future__ import annotations

from diagonal_motion import FRAMES, camera_plan


def install_cameras(world, carla, on_frame):
    """Install all four RGB streams; release any partial installation on error."""
    actors = []
    try:
        for item in camera_plan():
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(item["width"]))
            blueprint.set_attribute("image_size_y", str(item["height"]))
            blueprint.set_attribute("sensor_tick", "0.05")
            location = carla.Location(*item["location_xyz_m"])
            rotation = carla.Rotation(*item["rotation_pitch_yaw_roll_deg"])
            sensor = world.spawn_actor(blueprint, carla.Transform(location, rotation))
            if sensor is None:
                raise ValueError("camera spawn failed: " + item["name"])
            sensor.listen(lambda image, name=item["name"]: on_frame(name, image))
            actors.append((item["name"], sensor))
        return actors
    except Exception:
        for _, actor in reversed(actors):
            actor.stop()
            actor.destroy()
        raise


def validate_frame_map(frames: list[dict]) -> dict:
    """Require one source image from each sensor at each original Native frame."""
    expected = {item["name"]: item for item in camera_plan()}
    if len(frames) != FRAMES * len(expected):
        raise ValueError("four complete source-camera streams required")
    seen = set()
    for item in frames:
        name = item.get("camera")
        frame = item.get("frame")
        if name not in expected or type(frame) is not int or not 0 <= frame < FRAMES:
            raise ValueError("camera/frame identity changed")
        key = (name, frame)
        if key in seen:
            raise ValueError("duplicate source-camera frame")
        seen.add(key)
        if (item.get("native_frame") != frame or item.get("time_s") != frame / 20 or
                item.get("width") != expected[name]["width"] or
                item.get("height") != expected[name]["height"] or
                not item.get("source_path") or not item.get("source_sha256")):
            raise ValueError("camera source/frame join changed")
    if seen != {(name, frame) for name in expected for frame in range(FRAMES)}:
        raise ValueError("missing source-camera frame")
    return {"frames_per_camera": FRAMES, "camera_names": sorted(expected),
            "source_camera_frames": len(seen), "actual_pixels_reviewed": False}
