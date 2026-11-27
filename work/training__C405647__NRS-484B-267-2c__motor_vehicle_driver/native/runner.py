"""Prospective original Native acquisition for the exact emergency-approach pair.

CPU ``--check`` validates the authored request. A physical run requires an idle,
exclusive CARLA server and writes all temporary media outside ``work/``.
Original pixels and independent review are required before acceptance.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import traceback

from scene import ASSIGNMENT, CASES, CAMERA_DIMENSIONS, check_pair, request


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check(case):
    if case not in CASES:
        raise ValueError("Unknown exact case")
    pair = [request(name) for name in CASES]
    check_pair(*pair)
    item = request(case)
    saved = HERE / "requests" / (case + ".json")
    if json.loads(saved.read_text()) != item:
        raise ValueError("Saved source request differs from exact scene")
    if {c["name"]: (c["width"], c["height"]) for c in item["cameras"]} != CAMERA_DIMENSIONS:
        raise ValueError("Camera profile mismatch")
    return {"passed": True, "case_id": item["case_id"],
            "request_sha256": sha(saved.read_bytes()),
            "frames": item["frames"], "camera_count": 4,
            "carla_imported": False, "physical_acceptance_claimed": False}


def _native_location(carla, authored):
    return carla.Location(x=authored[0], y=-authored[1], z=authored[2])


def _camera_pose(carla, name):
    locations = {
        "overview": (-20, -20, 35),
        "approach": (-25, -8, 6),
        "reference_corner": (10, -12, 8),
        "driver_reference": (-65, -1.75, 5),
    }
    x, authored_y, z = locations[name]
    y = -authored_y
    aim_x, aim_y, aim_z = 15, 5, 1.5
    yaw = math.degrees(math.atan2(aim_y - y, aim_x - x))
    pitch = math.degrees(math.atan2(aim_z - z, math.hypot(aim_x - x, aim_y - y)))
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(yaw=yaw, pitch=pitch))


def _write_once(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _speed(actor):
    velocity = actor.get_velocity()
    return math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)


def _body_xy(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    return [[vertex.x, vertex.y] for vertex in vertices]


def execute(case, output, host, port):
    check(case)
    root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
    scratch = (REPO / ".runtime-work").resolve()
    output = Path(output).resolve()
    if not root.is_relative_to(scratch) or not output.is_relative_to(scratch):
        raise ValueError("Set output root and capture output under .runtime-work")
    if not output.is_dir() or any(output.iterdir()):
        raise ValueError("Capture output must be an existing empty scratch directory")
    sys.path.insert(0, str(REPO / "runtime"))
    import carla
    import numpy as np
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    item = request(case)
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    world = client.get_world()
    if saved["settings"].synchronous_mode or any(
            actor.type_id.startswith(("vehicle.", "walker.", "sensor."))
            for actor in world.get_actors()):
        raise RuntimeError("Exclusive idle asynchronous CARLA world required")
    actors, encoders, handles, cameras = [], {}, {}, {}
    changed, frames, error, restored = False, 0, None, None
    try:
        xml = item["source_map"]
        _write_once(output / "native-request.json", item)
        (output / "scene.xodr").write_text(xml + "\n")
        world = client.generate_opendrive_world(xml, carla.OpendriveGenerationParameters(
            vertex_distance=.25, max_road_length=50, wall_height=0,
            additional_width=0, smooth_junctions=False,
            enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        library = world.get_blueprint_library()
        ego_bp = library.find(item["ego_blueprint"])
        emergency_bp = library.find(item["emergency_blueprint"])
        ego_bp.set_attribute("role_name", "c405647_ego")
        emergency_bp.set_attribute("role_name", "c405647_emergency_request")
        ego = world.spawn_actor(ego_bp, carla.Transform(
            _native_location(carla, item["ego_start_xyz_m"])))
        actors.append(ego)
        emergency = world.spawn_actor(emergency_bp, carla.Transform(
            _native_location(carla, item["emergency_start_xyz_m"])))
        actors.append(emergency)
        ego.apply_control(carla.VehicleControl(brake=1))
        emergency.apply_control(carla.VehicleControl(brake=1))
        for _ in range(30):
            world.tick()
        mapping = world.get_map()
        for name, actor, lane_type in (("ego", ego, carla.LaneType.Driving),
                                       ("emergency", emergency, carla.LaneType.Shoulder)):
            waypoint = mapping.get_waypoint(actor.get_location(), project_to_road=False,
                                            lane_type=lane_type)
            if waypoint is None or waypoint.road_id != item["road_id"]:
                raise RuntimeError(name + " is not on its requested Native road lane")
        _write_once(output / "native-map-readback.json", {
            "original_opendrive_sha256": sha(mapping.to_opendrive().encode()),
            "requested_map_sha256": sha(xml.encode()),
            "initial_road_id": item["road_id"], "physical_acceptance_claimed": False})
        for spec in item["cameras"]:
            name = spec["name"]
            bp = library.find("sensor.camera.rgb")
            for attr, value in (("image_size_x", spec["width"]),
                                ("image_size_y", spec["height"]),
                                ("sensor_tick", 0)):
                bp.set_attribute(attr, str(value))
            camera = world.spawn_actor(bp, _camera_pose(carla, name))
            actors.append(camera)
            cameras[name] = queue.Queue()
            camera.listen(cameras[name].put)
            handles[name] = (output / (name + ".encoder.log")).open("x")
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                f"{spec['width']}x{spec['height']}", "-r", "20", "-i", "pipe:0",
                "-an", "-c:v", "ffv1", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=handles[name])
        with (output / "observed-actors.jsonl").open("x") as observed_file, \
             (output / "video_frames.jsonl").open("x") as frame_file:
            for index in range(item["frames"]):
                target = item["ego_response_policy"]
                brake = target["brake_command"] if (target["brake_onset_frame"] is not None
                           and index >= target["brake_onset_frame"]) else 0.0
                cruise_error = item["ego_cruise_speed_mps"] - _speed(ego)
                throttle = 0 if brake else max(0, min(.45, .15 + .25 * cruise_error))
                ego.apply_control(carla.VehicleControl(throttle=throttle, brake=brake))
                emergency.apply_control(carla.VehicleControl(
                    throttle=.15 if index >= item["emergency_motion_start_frame"] else 0,
                    brake=0 if index >= item["emergency_motion_start_frame"] else 1))
                requested_lamp = index % 10 < 5
                emergency.set_light_state(carla.VehicleLightState(
                    carla.VehicleLightState.Special1 if requested_lamp else
                    carla.VehicleLightState.NONE))
                native_frame = world.tick()
                timestamp = world.get_snapshot().timestamp.elapsed_seconds
                observed = {name: {"native_center_xy_m": [actor.get_location().x,
                                                           actor.get_location().y],
                                   "native_body_xy_m": _body_xy(actor),
                                   "native_speed_mps": _speed(actor),
                                   "native_yaw_deg": actor.get_transform().rotation.yaw}
                            for name, actor in (("ego", ego), ("emergency", emergency))}
                observed_file.write(json.dumps({"frame": index,
                    "native_frame": native_frame, "time_s": timestamp,
                    "source_kind": "original_native_motion", "actors": observed,
                    "ego_brake_request": brake,
                    "ego_cruise_throttle_request": throttle,
                    "ego_brake_observed": ego.get_control().brake,
                    "lamp_request": requested_lamp,
                    "lamp_state_observed": bool(emergency.get_light_state() &
                                                carla.VehicleLightState.Special1),
                    "light_qualification": "pending_independent_source_review"}) + "\n")
                for spec in item["cameras"]:
                    name = spec["name"]
                    image = cameras[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = cameras[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError("Original camera and Native frame join failed")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec["height"], spec["width"], 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                frame_file.write(json.dumps({"video_frame": index,
                    "native_frame": native_frame, "time_s": index / 20}) + "\n")
                frames += 1
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        for name, process in encoders.items():
            try:
                process.stdin.close()
                if process.wait(timeout=180):
                    raise RuntimeError(name + " lossless encoder failed")
            except BaseException as exc:
                error = error or {"encoder_error": str(exc)}
            handles[name].close()
        for actor in reversed(actors):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"cleanup_error": str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {"restore_error": str(exc)}
        _write_once(output / "native-capture-report.json", {
            "case_id": item["case_id"], "frames": frames,
            "expected_frames": item["frames"], "error": error,
            "restoration": restored, "accepted": False,
            "original_pixel_review_required": True,
            "vehicle_and_lamp_qualification_required": True})
    if error or frames != item["frames"]:
        raise RuntimeError("Native capture incomplete; inspect scratch report")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(args.case), sort_keys=True))
    else:
        if args.output_dir is None:
            parser.error("--output-dir is required for physical capture")
        execute(args.case, args.output_dir, args.host, args.port)
