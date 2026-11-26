"""Prospective original Native school-crossing capture for two exact cases.

No physical success is claimed before an operator runs and audits the scene.
The offline path validates the scene request without importing CARLA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback
import xml.etree.ElementTree as ET

from cameras import camera_plan
from geometry import CROSSWALK_NEAR_X_M, CROSSWALK_WIDTH_M, SIGN_X_M, check as geometry_check, open_drive


ROOT = Path(__file__).resolve().parent
CASES = {
    "condition_a": "entry_during_crossing",
    "condition_b": "entry_after_crossing",
}


def write_new(path: Path, value: object) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def check(config: dict) -> dict:
    suffix = config.get("case_id", "").split("__")[-1]
    if suffix not in CASES or config.get("condition") != CASES[suffix]:
        raise ValueError("Exact school-crossing case differs")
    if config.get("selected_case_id") != config["case_id"] or (
        config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "LVMC-11-18-020", "C394563", "motor_vehicle_driver"):
        raise ValueError("Law, cell or actor differs")
    if (config.get("rate_hz"), config.get("duration_frames"), config.get("duration_s")) != (20, 600, 30):
        raise ValueError("Exact four-view duration differs")
    if (config.get("school_xing_sign_x_m"), config.get("crosswalk_x_m"),
        config.get("crosswalk_width_m")) != (SIGN_X_M, CROSSWALK_NEAR_X_M,
                                             CROSSWALK_WIDTH_M):
        raise ValueError("School-Xing sign/crossing configuration differs")
    physical = config.get("physical_completion", {})
    if (physical.get("criterion"), physical.get("motion_source"),
        physical.get("body_key")) != ("intersection_clearance", "body_history.jsonl",
                                      "body_vertices_m"):
        raise ValueError("Source-bound crossing clearance criterion missing")
    cameras = camera_plan()
    if [(c["width"], c["height"]) for c in cameras] != [
        (1920, 1080), (1280, 720), (1280, 720), (1280, 720)]:
        raise ValueError("Four source camera profile differs")
    geometry = geometry_check()
    return {"case_id": config["case_id"], "geometry": geometry,
            "cameras": cameras, "native_imported": False,
            "physical_completion_claimed": False}


def camera_transform(carla, spec):
    x, y, z = spec["xyz_m"]
    if spec["attachment"] == "world":
        target = (0.0, -1.0, 0.0)
        yaw = math.degrees(math.atan2(target[1] - y, target[0] - x))
        pitch = math.degrees(math.atan2(target[2] - z, math.hypot(target[0] - x, target[1] - y)))
    else:
        yaw, pitch = 0.0, -7.0
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(yaw=yaw, pitch=pitch))


def footprint(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = sorted({(round(v.x, 5), round(v.y, 5)) for v in vertices})
    if len(points) != 4:
        raise RuntimeError("Original ego body does not have four horizontal corners")
    return [list(p) for p in points]


def native_survey(carla, mapping) -> dict:
    observed_xml = mapping.to_opendrive()
    root = ET.fromstring(observed_xml)
    sign = root.find(".//object[@name='School-Xing']")
    crossing = root.find(".//object[@name='yellow-school-crosswalk']")
    if sign is None or crossing is None:
        raise RuntimeError("Native map lost school sign or crosswalk object")
    near = float(crossing.attrib["s"]) - 100.0
    sign_x = float(sign.attrib["s"]) - 100.0
    width = float(crossing.attrib["length"])
    if abs(near - CROSSWALK_NEAR_X_M) > .05 or abs(width - CROSSWALK_WIDTH_M) > .05 or (
        near - sign_x < 30.48 or crossing.attrib.get("color") != "yellow"):
        raise RuntimeError("Native school sign/crossing geometry differs")
    for name, y, lane_id, direction in (("approach", -1.75, -1, 1),
                                         ("opposing", 1.75, 1, -1)):
        waypoint = mapping.get_waypoint(carla.Location(x=-20, y=y, z=.2),
                                        project_to_road=False, lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.lane_id != lane_id:
            raise RuntimeError("Native school road lane survey failed: " + name)
        forward = waypoint.transform.get_forward_vector()
        if forward.x * direction < .98:
            raise RuntimeError("Native school road direction differs: " + name)
    return {"native_map_sha256": hashlib.sha256(observed_xml.encode()).hexdigest(),
            "native_map_object_readback": True,
            "crosswalk": {"near_x_m": near,
                          "width_along_road_m": width,
                          "low_y_m": -3.5, "high_y_m": 3.5,
                          "marked_yellow": True},
            "school_xing_sign": {"legend": sign.attrib["name"], "x_m": sign_x,
                                  "native_map_object_present": True,
                                  "displayed_pixels_verified": False},
            "rendered_sign_text_verified": False,
            "city_traffic_engineer_authority_verified": False}


def execute(config: dict, output: Path, host: str, port: int) -> None:
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot

    check(config)
    output = output.resolve()
    if not output.is_dir() or not (output / "config.json").is_file():
        raise ValueError("Use a fresh materialized exact-case output")
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    prior = client.get_world()
    if saved["settings"].synchronous_mode or [a for a in prior.get_actors()
        if a.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))]:
        raise RuntimeError("Requires exclusive idle asynchronous Native world")
    owned = []
    encoders = {}
    encoder_logs = {}
    camera_queues = {}
    capture = None
    restoration = None
    error = None
    frames = 0
    encoder_exit_codes = {}
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.25, max_road_length=50, wall_height=0,
            additional_width=0, smooth_junctions=False,
            enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        readback = native_survey(carla, world.get_map())
        write_new(output / "road_geometry.json", readback)
        library = world.get_blueprint_library()
        vehicle_bp = library.find("vehicle.lincoln.mkz_2020")
        vehicle_bp.set_attribute("role_name", "c394563_ego")
        ego = world.spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(x=-50, y=-1.75, z=.5), carla.Rotation(yaw=0)))
        owned.append(ego)
        walker_bp = next(bp for bp in library.filter("walker.pedestrian.*"))
        walker = world.spawn_actor(walker_bp, carla.Transform(
            carla.Location(x=1.5, y=-4.0, z=.4), carla.Rotation(yaw=90)))
        owned.append(walker)
        write_new(output / "native-construction-context.json", {
            "case_id": config["case_id"], "ego_actor_id": ego.id,
            "ego_blueprint": ego.type_id, "pedestrian_actor_id": walker.id,
            "pedestrian_blueprint": walker.type_id,
            "native_map_sha256": readback["native_map_sha256"],
            "school_sign_pixels_verified": False,
            "city_marking_authority_verified": False,
            "pedestrian_intent_verified": False})
        for spec in camera_plan():
            blueprint = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", spec["width"]),
                               ("image_size_y", spec["height"]),
                               ("fov", spec["fov_deg"]), ("sensor_tick", 0)):
                blueprint.set_attribute(key, str(value))
            sensor = world.spawn_actor(blueprint, camera_transform(carla, spec),
                attach_to=ego if spec["attachment"] == "ego" else None)
            owned.append(sensor)
            camera_queues[spec["name"]] = queue.Queue()
            sensor.listen(camera_queues[spec["name"]].put)
            encoder_logs[spec["name"]] = (output / (spec["name"] + ".encoder.log")).open("x")
            encoders[spec["name"]] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                f"{spec['width']}x{spec['height']}", "-r", "20", "-i", "pipe:0",
                "-an", "-c:v", "ffv1", "-level", "1",
                str(output / (spec["name"] + ".mkv"))],
                stdin=subprocess.PIPE, stderr=encoder_logs[spec["name"]])
        capture = PipelineCapture(client, ego, output, config["case_id"],
                                  visibility=False,
                                  required_observations=config.get("required_atoms", []))
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / "native_samples.jsonl").open("x") as samples, \
             (output / "body_history.jsonl").open("x") as body_history, \
             FrameMap(output / "video_frames.jsonl") as frame_map:
            for index in range(600):
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.hypot(velocity.x, velocity.y)
                if 230 <= index < 340:
                    walker.apply_control(carla.WalkerControl(
                        direction=carla.Vector3D(0, 1, 0), speed=1.5))
                else:
                    walker.apply_control(carla.WalkerControl(
                        direction=carla.Vector3D(0, 0, 0), speed=0.0))
                hold = (config["condition"] == "entry_after_crossing" and
                        index < 340 and max(p[0] for p in footprint(ego)) >= -8.0)
                command = {"throttle": 0.0 if hold else min(.55, max(0.0, .28 + .18 * (3.5-speed))),
                           "brake": 1.0 if hold else max(0.0, .35 * (speed-3.5)),
                           "steer": max(-.3, min(.3, -.12 * (pose.location.y + 1.75)
                                                - .015 * pose.rotation.yaw)),
                           "hand_brake": False}
                ego.apply_control(carla.VehicleControl(**command))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = ego.get_transform()
                pedestrian = walker.get_transform().location
                pvelocity = walker.get_velocity()
                body = footprint(ego)
                sample = {"source_kind": "original_native_actor_readback",
                          "native_frame": frame, "time_s": time_s,
                          "ego_body_xy_m": body,
                          "ego_center_xy_m": [pose.location.x, pose.location.y],
                          "person": {"actor_id": walker.id, "actor_kind": "walker",
                                     "center_x_m": pedestrian.x,
                                     "center_y_m": pedestrian.y,
                                     "velocity_y_mps": pvelocity.y},
                          "controller_request": command}
                capture.capture(frame, time_s, extra={"school_crossing_native": sample})
                samples.write(json.dumps(sample, allow_nan=False) + "\n")
                body_history.write(json.dumps({"frame": frame, "time_s": time_s,
                    "body_vertices_m": body, "pedestrian_actor_id": walker.id},
                    allow_nan=False) + "\n")
                joined = {}
                for spec in camera_plan():
                    image = camera_queues[spec["name"]].get(timeout=30)
                    while image.frame < frame:
                        image = camera_queues[spec["name"]].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError("Original camera frame join failed")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec["height"], spec["width"], 4)[:, :, :3][:, :, ::-1]
                    encoders[spec["name"]].stdin.write(rgb.tobytes())
                    joined[spec["name"]] = image.frame
                frame_map.append(frame, time_s, camera_frames=joined)
                frames += 1
        if frames != 600:
            raise RuntimeError("Incomplete 600-frame original source capture")
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {"capture_close_error": str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                encoder_exit_codes[name] = encoder.wait(timeout=180)
                if encoder_exit_codes[name] != 0:
                    raise RuntimeError("Source video encoder failed: " + name)
            except BaseException as exc:
                error = error or {"encoder_error": str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"owned_actor_cleanup_error": str(exc)}
        try:
            restoration = restore(client, saved)
        except BaseException as exc:
            error = error or {"world_restore_error": str(exc)}
        write_new(output / "native-capture-report.json", {
            "case_id": config["case_id"], "frames": frames,
            "expected_frames": 600, "encoder_exit_codes": encoder_exit_codes,
            "restoration": restoration, "error": error,
            "physical_acceptance_claimed": False})
    if error:
        raise RuntimeError("Native school-crossing attempt failed; see native-capture-report.json")
    seal_capture(output, frames=frames, restoration=restoration, errors=None,
                 encoder_exit_codes=encoder_exit_codes,
                 context={"case_id": config["case_id"], "school_sign_pixels_verified": False})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error("Supply output-dir, host and port")
        execute(config, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
