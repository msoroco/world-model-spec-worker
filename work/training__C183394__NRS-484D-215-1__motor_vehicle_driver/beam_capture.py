"""Original Native acquisition request for the two C183394 beam cases.

The local operator supplies an exclusive CARLA world. Every failure retains an
attempt report. The source rows preserve lamp readback and four video joins;
they do not claim an emitted ray, an actual driver-eye region or legal result.
"""
import hashlib
import json
import math
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import traceback

from beam_native import command_tick, install
from saved_beam import CAMERAS, SOURCES


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def repository():
    for parent in Path(__file__).resolve().parents:
        if (parent / "batch.json").is_file():
            return parent
    raise RuntimeError("Pinned repository unavailable")


def run(bundle, output, host, port):
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file() or \
            not (output / "runner.py").is_file() or not (output / "config.json").is_file():
        raise ValueError("Native attempt must be a fresh materialized construction")
    if (output / "capture").exists() or (output / "native-capture-report.json").exists():
        raise ValueError("Retain prior Native attempt; use fresh materialization")
    root = repository()
    sys.path.insert(0, str(root / "runtime/scenario_pipeline"))
    sys.path.insert(1, str(root / "runtime/python"))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.media import compose_four_views
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    config = json.loads((output / "config.json").read_text())
    case = config["selected_case_id"]
    if case not in config["supported_case_ids"] or not case.endswith(
            ("__condition_a", "__condition_b")):
        raise ValueError("Exact beam case unsupported")
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    original = client.get_world()
    if saved["settings"].synchronous_mode or any(
            actor.type_id.startswith(("vehicle.", "walker.", "sensor."))
            for actor in original.get_actors()):
        raise RuntimeError("Exclusive idle asynchronous CARLA world required")
    scene = None
    owned, encoders, encoder_logs, feeds = [], {}, {}, {}
    capture = None
    count, error, restored, world_changed = 0, None, None, False
    try:
        world_changed = True
        scene = install(client, carla, "condition_a" if case.endswith("__condition_a")
                        else "condition_b", config["acceleration_gain"])
        world = scene["world"]
        owned.extend(scene["owned"])
        for _ in range(20):
            world.tick()
        plan = scene["plan"]
        for camera in plan["cameras"]:
            name = camera["name"]
            width, height = camera["size"]
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", 85), ("sensor_tick", 0)):
                bp.set_attribute(key, str(value))
            xyz = camera["xyz_m"]
            transform = carla.Transform(carla.Location(*xyz), carla.Rotation(
                yaw=camera["yaw_deg"], pitch=camera["pitch_deg"]))
            parent = scene.get(camera["mount"]) if camera["mount"] != "world" else None
            sensor = world.try_spawn_actor(bp, transform, attach_to=parent)
            if sensor is None:
                raise RuntimeError("Original camera spawn failed: " + name)
            owned.append(sensor)
            feeds[name] = queue.Queue()
            encoder_logs[name] = (output / (name + ".encoder.log")).open("x")
            encoders[name] = subprocess.Popen(["ffmpeg", "-nostdin", "-hide_banner",
                "-loglevel", "error", "-n", "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", f"{width}x{height}", "-r", "20", "-i", "pipe:0", "-an",
                "-c:v", "ffv1", "-level", "1", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=encoder_logs[name])
            sensor.listen(feeds[name].put)
        capture = PipelineCapture(client, scene["ego"], output, case,
                                  visibility=False, required_observations=[])
        road = scene["map"].to_opendrive()
        with (output / "road.xodr").open("x") as road_source:
            road_source.write(road)
        put(output / "road-position-source.json", {
            "road_position": "adjacent_shoulder",
            "map_and_adjacency_source": "original OpenDRIVE lane -2 shoulder and lane -1 adjoining driving readback",
            "native_map_sha256": hashlib.sha256(road.encode()).hexdigest(),
            "highway_status_review_required": True})
        put(output / "lighting-trigger-source.json", {
            "lighting_trigger": "night_interval",
            "original_trigger_source": "original simulator weather request and timestamp; dated Nevada sun-event review pending",
            "NRS_484D_100_review_required": True,
            "civil_time_condition_verified": False})
        put(output / "oncoming-driver-source.json", {
            "oncoming_actor_source": "original opposed vehicle transform and Native actor id",
            "actor_id": scene["oncoming"].id,
            "driver_eye_identity_review_required": True})
        put(output / "eye-region-source.json", {
            "driver_reference_camera": "driver_reference", "pixel_review_required": True,
            "original_driver_eye_region_verified": False})
        start = world.get_snapshot().timestamp.elapsed_seconds + .05
        with (output / "beam-rows.jsonl").open("x") as rows, \
             (output / "video_frames.jsonl").open("x") as mapping:
            for index in range(600):
                command = command_tick(scene, carla)
                native_frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                ego, other = scene["ego"], scene["oncoming"]
                ep, op = ego.get_transform(), other.get_transform()
                ev, ov = ego.get_velocity(), other.get_velocity()
                row = {"frame": index, "native_frame": native_frame, "time_s": time_s,
                    "ego_x_m": ep.location.x, "ego_y_m": ep.location.y,
                    "ego_heading_x": math.cos(math.radians(ep.rotation.yaw)),
                    "ego_heading_y": math.sin(math.radians(ep.rotation.yaw)),
                    "oncoming_x_m": op.location.x, "oncoming_y_m": op.location.y,
                    "oncoming_heading_x": math.cos(math.radians(op.rotation.yaw)),
                    "oncoming_heading_y": math.sin(math.radians(op.rotation.yaw)),
                    "ego_speed_mps": math.hypot(ev.x, ev.y),
                    "oncoming_speed_mps": math.hypot(ov.x, ov.y),
                    "requested_beam_state": command["requested_beam_state"],
                    "lamp_state_source": "Vehicle.get_light_state",
                    "observed_light_state_bits": int(ego.get_light_state()),
                    "eye_region_pixels_retained": True}
                capture.capture(native_frame, time_s, extra={"c183394_beam": row})
                rows.write(json.dumps(row, allow_nan=False) + "\n")
                for camera in plan["cameras"]:
                    name = camera["name"]
                    width, height = camera["size"]
                    image = feeds[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = feeds[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError("Original camera/Native frame join differs")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                mapping.write(json.dumps({"video_frame": index,
                    "native_frame": native_frame, "carla_frame": native_frame,
                    "time_s": time_s}, allow_nan=False) + "\n")
                count += 1
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {"capture_close_error": str(exc)}
        for name, process in encoders.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180) != 0:
                    raise RuntimeError("Lossless encoder failed: " + name)
            except BaseException as exc:
                error = error or {"encoder_error": str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"cleanup_error": str(exc)}
        if world_changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {"restore_error": str(exc)}
        if error is None and count == 600:
            try:
                put(output / "acquisition-provenance.json", {
                    "provenance_kind": "native", "diagnostic_fixture": False})
                files = {name: digest(output / name) for name in SOURCES}
                put(output / "beam-context.json", {"case_id": case,
                    "source_sha256": files, "deeming_invoked": False,
                    "legal_verdict_claimed": False})
                views = {slot: output / (name + ".mkv") for slot, name in zip(
                    ("overview", "approach", "reference_corner", "driver_reference"), CAMERAS)}
                put(output / "four-view-receipt.json", compose_four_views(
                    views, output / "video_frames.jsonl", output / "raw.mkv"))
                seal_capture(output, frames=count, restoration=restored, errors=[],
                    encoder_exit_codes={name: p.returncode for name, p in encoders.items()},
                    context={"case_id": case, "candidate_id": config["candidate_id"],
                             "physical_acceptance_claimed": False})
            except BaseException as exc:
                error = error or {"seal_error": str(exc)}
        put(output / "native-capture-report.json", {"case_id": case,
            "requested_frames": 600, "observed_frames": count,
            "restoration": restored, "error": error,
            "physical_acceptance_claimed": False})
    if error:
        raise RuntimeError("Native beam attempt failed; see native-capture-report.json")
