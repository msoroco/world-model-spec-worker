"""Four original Native RGB source streams with exact frame joins.

No synthetic media substitutes for a missing camera frame. The caller must
seal actual capture and assess pixels before any physical claim.
"""

import json
import math
import subprocess
from contextlib import contextmanager
from pathlib import Path
from queue import Empty


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def validate_plan(path):
    path = Path(path)
    plan = json.loads(path.read_text())
    if plan.get("format") != "c24811-four-camera-native-capture-plan-v1" or plan.get("rate_hz") != 20:
        raise ValueError("Pinned four-camera source plan required")
    if type(plan.get("duration_s")) is not int or not 5 <= plan["duration_s"] <= 120:
        raise ValueError("Bounded Native capture duration required")
    site = json.loads(path.with_name("blind-site-candidate.json").read_text())
    if plan.get("map_sha256") != site["map"]["sha256"]:
        raise ValueError("Camera plan map differs from site")
    cameras = plan.get("cameras")
    if not isinstance(cameras, list) or tuple(row.get("name") for row in cameras) != CAMERAS:
        raise ValueError("Four named original source cameras required")
    for row in cameras:
        if (row.get("width"), row.get("height")) != SIZES[row["name"]]:
            raise ValueError("Source camera dimensions differ from pinned profile")
        pose = row.get("pose")
        if (not isinstance(pose, dict) or set(pose) != {"x", "y", "z", "yaw", "pitch"} or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in pose.values()) or
                type(row.get("fov_deg")) not in (int, float) or not 20 <= row["fov_deg"] <= 120 or
                not row.get("pose_strategy")):
            raise ValueError("Finite source camera pose, FOV and strategy required")
    required = {"trace.jsonl", "vehicle_signal_history.jsonl", "video_frames.jsonl",
                "junction_context.json", "capture/evidence.jsonl"}
    if set(plan.get("raw_sources", [])) != required:
        raise ValueError("Complete raw source inventory required")
    return {"names": list(CAMERAS), "rate_hz": 20,
            "frames_planned": plan["duration_s"]*20,
            "native_pixels_verified": False}


def source_camera_frame(queue, expected_frame):
    if type(expected_frame) is not int or expected_frame < 0:
        raise ValueError("Nonnegative Native frame required")
    for _ in range(8):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError("Source camera frame missing") from error
        if image.frame == expected_frame:
            return bytes(image.raw_data)
        if image.frame > expected_frame:
            raise ValueError("Source camera skipped Native frame")
    raise ValueError("Source camera frame join failed")


@contextmanager
def source_cameras(world, ego, carla, plan):
    sensors = {}
    try:
        for row in plan["cameras"]:
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", row["width"]),
                               ("image_size_y", row["height"]),
                               ("fov", row["fov_deg"]), ("sensor_tick", 0.05)):
                blueprint.set_attribute(key, str(value))
            pose = row["pose"]
            transform = carla.Transform(
                carla.Location(x=pose["x"], y=pose["y"], z=pose["z"]),
                carla.Rotation(yaw=pose["yaw"], pitch=pose["pitch"]))
            kwargs = {"attach_to": ego} if row["name"] == "driver_reference" else {}
            sensor = world.spawn_actor(blueprint, transform, **kwargs)
            if sensor is None:
                raise ValueError("Native source camera spawn failed: " + row["name"])
            sensors[row["name"]] = sensor
        yield sensors
    finally:
        for sensor in reversed(list(sensors.values())):
            sensor.stop()
            sensor.destroy()


@contextmanager
def ffv1_writer(path, size):
    path = Path(path)
    width, height = size
    if path.exists() or type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise ValueError("Fresh finite-size source video required")
    process = subprocess.Popen([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-f", "rawvideo",
        "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
        "-framerate", "20", "-i", "pipe:0", "-an", "-c:v", "ffv1",
        "-level", "3", "-pix_fmt", "bgr0", str(path)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    count = 0
    def write(data):
        nonlocal count
        if len(data) != width*height*4 or process.poll() is not None:
            raise ValueError("Source-camera BGRA size or encoder mismatch")
        process.stdin.write(data)
        count += 1
    try:
        yield write
    finally:
        process.stdin.close()
        code = process.wait(timeout=60)
        stderr = process.stderr.read().decode(errors="replace")
        process.stderr.close()
        if code or count == 0:
            raise ValueError("Native FFV1 encoder failed: " + stderr[-500:])


if __name__ == "__main__":
    print(json.dumps(validate_plan(Path(__file__).with_name("capture-plan.json")), indent=2))
