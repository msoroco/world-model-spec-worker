"""Retain synchronized Native turn-signal sources for saved processing.

The recorder accepts only camera images and actor state from the same CARLA
snapshot. It creates no derived observation channels or synthetic video.
"""

import json
import math
import subprocess
from contextlib import ExitStack, contextmanager
from pathlib import Path
from queue import Empty


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
RATE_HZ = 20


def _finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Nonfinite Native source value")
    return float(value)


def source_camera_frame(queue, expected_frame):
    if type(expected_frame) is not int or expected_frame < 0:
        raise ValueError("Nonnegative Native frame required")
    for _ in range(8):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError("Original camera frame missing") from error
        if image.frame == expected_frame:
            return bytes(image.raw_data)
        if image.frame > expected_frame:
            raise ValueError("Original camera skipped Native frame")
    raise ValueError("Original camera frame join failed")


def source_row(snapshot, actor, carla, waypoint=None):
    frame = snapshot.frame
    time_s = snapshot.timestamp.elapsed_seconds
    if type(frame) is not int or frame < 0:
        raise ValueError("Invalid Native snapshot frame")
    position = actor.get_location()
    velocity = actor.get_velocity()
    transform = actor.get_transform()
    heading = transform.rotation.yaw
    vertices = actor.bounding_box.get_world_vertices(transform)
    if len(vertices) < 4:
        raise ValueError("Complete original Native body geometry required")
    state = actor.get_light_state()
    row = {"frame": frame, "time_s": _finite(time_s),
            "ego_position_xy_m": [_finite(position.x), _finite(position.y)],
            "ego_speed_mps": math.hypot(_finite(velocity.x), _finite(velocity.y)),
            "ego_heading_deg": _finite(heading),
            "body_vertices_m": [[_finite(vertex.x), _finite(vertex.y)]
                                for vertex in vertices],
            "right_indicator": bool(state & carla.VehicleLightState.RightBlinker),
            "native_actor_id": actor.id}
    if waypoint is not None:
        row["ego_road_id"] = waypoint.road_id
        row["ego_lane_id"] = waypoint.lane_id
    return row


def validate_plan(plan):
    if not isinstance(plan, dict) or plan.get("rate_hz") != RATE_HZ or not 5 <= plan.get("duration_s", 0) <= 120:
        raise ValueError("Pinned bounded Native camera plan required")
    cameras = plan.get("cameras")
    if not isinstance(cameras, list) or tuple(row.get("name") for row in cameras) != CAMERAS:
        raise ValueError("Four named original source cameras required")
    for row in cameras:
        if (row.get("width"), row.get("height")) != SIZES[row["name"]]:
            raise ValueError("Original source-camera dimensions differ")
        pose = row.get("pose")
        if not isinstance(pose, dict) or set(pose) != {"x", "y", "z", "yaw", "pitch"}:
            raise ValueError("Complete Native camera pose required")
        for value in pose.values():
            _finite(value)
        if not 20 <= _finite(row.get("fov_deg")) <= 120:
            raise ValueError("Native camera FOV invalid")
    return {"frames_planned": plan["duration_s"] * RATE_HZ,
            "native_pixels_verified": False}


@contextmanager
def source_cameras(world, ego, carla, plan):
    validate_plan(plan)
    sensors = {}
    try:
        for row in plan["cameras"]:
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", row["width"]),
                               ("image_size_y", row["height"]),
                               ("fov", row["fov_deg"]), ("sensor_tick", 1/RATE_HZ)):
                blueprint.set_attribute(key, str(value))
            pose = row["pose"]
            transform = carla.Transform(
                carla.Location(x=pose["x"], y=pose["y"], z=pose["z"]),
                carla.Rotation(yaw=pose["yaw"], pitch=pose["pitch"]))
            kwargs = {"attach_to": ego} if row["name"] == "driver_reference" else {}
            sensor = world.spawn_actor(blueprint, transform, **kwargs)
            if sensor is None:
                raise ValueError("Original source camera spawn failed")
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
        raise ValueError("Fresh original source video required")
    process = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-f", "rawvideo",
         "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
         "-framerate", str(RATE_HZ), "-i", "pipe:0", "-an", "-c:v", "ffv1",
         "-level", "3", "-pix_fmt", "bgr0", str(path)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    count = 0
    def write(data):
        nonlocal count
        if len(data) != width * height * 4 or process.poll() is not None:
            raise ValueError("Original BGRA source size or encoder mismatch")
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
            raise ValueError("Original source FFV1 encoding failed: " + stderr[-500:])


@contextmanager
def source_recorder(output, sizes=None):
    """Write one frame map and drive history alongside four lossless streams."""
    output = Path(output).resolve()
    repo = next((parent for parent in Path(__file__).resolve().parents
                 if (parent / "batch.json").is_file() and (parent / "runtime.py").is_file()), None)
    if repo is None or not output.is_relative_to(repo / ".runtime-work"):
        raise ValueError("Native source output must be ignored runtime work")
    if not output.is_dir():
        raise ValueError("Materialized Native attempt directory required")
    owned = [output / (camera + ".mkv") for camera in CAMERAS]
    owned += [output / "drive_history.jsonl", output / "video_frames.jsonl"]
    if any(path.exists() for path in owned):
        raise ValueError("Fresh original source paths required")
    sizes = SIZES if sizes is None else sizes
    if set(sizes) != set(CAMERAS):
        raise ValueError("Four original source sizes required")
    with ExitStack() as stack:
        writers = {camera: stack.enter_context(ffv1_writer(output / (camera + ".mkv"), sizes[camera]))
                   for camera in CAMERAS}
        history = stack.enter_context((output / "drive_history.jsonl").open("x", buffering=1))
        frame_map = stack.enter_context((output / "video_frames.jsonl").open("x", buffering=1))
        prior = [-1, -math.inf]
        index = [0]
        def append(snapshot, actor, carla, queues, waypoint=None):
            row = source_row(snapshot, actor, carla, waypoint)
            if row["frame"] <= prior[0] or row["time_s"] <= prior[1]:
                raise ValueError("Nonmonotone Native snapshot")
            if set(queues) != set(CAMERAS):
                raise ValueError("Four original camera queues required")
            pixels = {name: source_camera_frame(queues[name], row["frame"]) for name in CAMERAS}
            if any(len(pixels[name]) != sizes[name][0] * sizes[name][1] * 4 for name in CAMERAS):
                raise ValueError("Original camera dimensions differ from plan")
            for name in CAMERAS:
                writers[name](pixels[name])
            history.write(json.dumps(row, allow_nan=False) + "\n")
            frame_map.write(json.dumps({"video_frame": index[0], "carla_frame": row["frame"],
                                        "time_s": row["time_s"]}, allow_nan=False) + "\n")
            prior[:] = [row["frame"], row["time_s"]]
            index[0] += 1
        yield append
