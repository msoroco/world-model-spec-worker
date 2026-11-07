"""Proposed original CARLA capture for C111294 NRS 484B.600(1)(e).

`--check` is CPU-only. `--execute` requires an owned idle CARLA endpoint and
records actual Native telemetry, four original camera streams and the pinned
Core capture. It has not been physically executed or accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import sys
import traceback

from cameras import camera_plan, check as cameras_check
from engineering import CANDIDATES, candidate_plan
from geometry import FPS, FRAMES, MPH_TO_MPS, SPEED_MPH, check as geometry_check, open_drive

ROOT = Path(__file__).resolve().parent
CHANNELS = ("ego_pose", "ego_speed", "observed_speed", "other_vehicle_pose")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_new(path: Path, value: object) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def check(case: str, candidate: str) -> dict:
    scene = geometry_check()
    camera = cameras_check()
    plan = candidate_plan(case, candidate)
    if plan["knobs"]["sample_rate_hz"] != FPS or plan["knobs"]["duration_s"] != FRAMES / FPS:
        raise ValueError("Candidate timebase differs from capture")
    if plan["knobs"]["camera_profile"] != [v["name"] for v in camera["views"]]:
        raise ValueError("Candidate camera identity differs from capture")
    if not 0 < plan["knobs"]["speed_pid_kp"] < 1 or not 0 < plan["knobs"]["brake_pid_kp"] < 1:
        raise ValueError("Unsupported speed feedback")
    if not 5 <= plan["knobs"]["steering_lookahead_m"] <= 15:
        raise ValueError("Unsupported steering lookahead")
    return {"passed": True, "case_id": plan["case_id"], "candidate": candidate,
            "requested_setting_mph": SPEED_MPH[case], "authored_map": scene,
            "camera_profile": camera, "channels": list(CHANNELS),
            "native_spawn_requests": {
                "ego": {"native_xy_m": [1.75, 70.0], "yaw_deg": -90,
                        "road_id": 1, "lane_id": -1},
                "other": {"native_xy_m": [-1.75, -100.0], "yaw_deg": 90,
                          "road_id": 4, "lane_id": 1}},
            "map_readback_pending": True, "native_capture_pending": True,
            "selected": False}


def control_command(speed_mps: float, lateral_error_m: float,
                    yaw_error_deg: float, target_mph: float, knobs: dict) -> dict:
    values = (speed_mps, lateral_error_m, yaw_error_deg, target_mph)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in values) or speed_mps < 0 or target_mph <= 0:
        raise ValueError("Invalid observed controller input")
    target = target_mph * MPH_TO_MPS
    error = (target - speed_mps) / target
    if error >= 0:
        throttle = max(0.0, min(1.0, .35 + knobs["speed_pid_kp"] * error))
        brake = 0.0
    else:
        throttle = 0.0
        brake = max(0.0, min(1.0, knobs["brake_pid_kp"] * (-error)))
    steer = max(-.35, min(.35, -lateral_error_m / knobs["steering_lookahead_m"]
                               - yaw_error_deg / 90.0))
    return {"throttle": throttle, "brake": brake, "steer": steer}


def native_sample(index: int, frame: int, elapsed_s: float, ego, other) -> dict:
    if type(index) is not int or not 0 <= index < FRAMES or type(frame) is not int or frame < 0:
        raise ValueError("Native frame identity absent")
    if not isinstance(elapsed_s, (int, float)) or not math.isfinite(elapsed_s):
        raise ValueError("Native time absent")
    et, ot = ego.get_transform(), other.get_transform()
    ev = ego.get_velocity()
    control = ego.get_control()
    if ego.type_id != "vehicle.tesla.model3" or other.type_id != "vehicle.tesla.model3":
        raise ValueError("Conventional vehicle blueprint changed")
    if (ego.attributes.get("role_name") != "c111294_speed_subject" or
            other.attributes.get("role_name") != "c111294_opposing_vehicle"):
        raise ValueError("Native subject or other actor role readback changed")
    return {"frame": index, "native_frame": frame, "t_s": index / FPS,
            "native_elapsed_s": elapsed_s,
            "ego_actor_id": ego.id, "other_actor_id": other.id,
            "ego_role": "motor_vehicle_driver", "other_role": "motor_vehicle_driver",
            "ego_role_name": ego.attributes["role_name"],
            "other_role_name": other.attributes["role_name"],
            "ego_blueprint": ego.type_id, "other_blueprint": other.type_id,
            "ego_position_m": [et.location.x, et.location.y, et.location.z],
            "other_position_m": [ot.location.x, ot.location.y, ot.location.z],
            "ego_heading_deg": et.rotation.yaw,
            "other_heading_deg": ot.rotation.yaw,
            "ego_velocity_mps": [ev.x, ev.y, ev.z],
            "ego_control": {name: getattr(control, name)
                            for name in ("throttle", "brake", "steer")},
            "ego_body_vertices_m": [[v.x, v.y, v.z] for v in
                                    ego.bounding_box.get_world_vertices(et)],
            "other_body_vertices_m": [[v.x, v.y, v.z] for v in
                                      other.bounding_box.get_world_vertices(ot)],
            "source_kind": "original_native_capture"}


def _survey(carla, mapping) -> dict:
    requests = {"ego": (1.75, 70.0, 1, -1, (0, -1)),
                "other": (-1.75, -100.0, 4, 1, (0, 1))}
    result = {}
    for name, (x, y, road_id, lane_id, direction) in requests.items():
        wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=.2),
                                  project_to_road=False, lane_type=carla.LaneType.Driving)
        if wp is None or (wp.road_id, wp.lane_id) != (road_id, lane_id):
            raise RuntimeError("Native road/lane readback failed: " + name)
        forward = wp.transform.get_forward_vector()
        if forward.x * direction[0] + forward.y * direction[1] < .98:
            raise RuntimeError("Native lane direction failed: " + name)
        if not 3.4 <= wp.lane_width <= 3.6:
            raise RuntimeError("Native lane width failed: " + name)
        result[name] = {"road_id": wp.road_id, "lane_id": wp.lane_id,
                        "lane_width_m": wp.lane_width,
                        "center_native_xy_m": [wp.transform.location.x,
                                               wp.transform.location.y]}
    return result


def execute(case: str, candidate: str, output_dir: Path, host: str, port: int) -> dict:
    import carla
    import numpy as np
    for parent in ROOT.parents:
        package = parent / "runtime/pipeline/scenario_pipeline"
        source = parent / "runtime/pipeline/python"
        if package.is_dir() and source.is_dir():
            sys.path[:0] = [str(package), str(source)]
            break
    from worker_exchange.world_restore import snapshot, restore
    from pipeline_capture import PipelineCapture

    preflight = check(case, candidate)
    plan = candidate_plan(case, candidate)
    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output / "config.json").is_file() or (output / "road.xodr").exists():
        raise ValueError("Use a fresh exact materialized case directory")
    config = json.loads((output / "config.json").read_text())
    if (config.get("case_id") != plan["case_id"] or
            config.get("candidate_id") != candidate or
            config.get("knobs") != plan["knobs"]):
        raise ValueError("Materialized case/candidate control differs")
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    old_world = client.get_world()
    if saved["settings"].synchronous_mode or any(a.type_id.startswith(
            ("vehicle.", "walker.", "sensor.", "controller.")) for a in old_world.get_actors()):
        raise RuntimeError("Requires exclusive idle asynchronous Native world")
    owned, encoders, logs, queues, channels = [], {}, {}, {}, {}
    capture = None
    changed, restored, error, frames = False, None, None, 0
    try:
        world = client.generate_opendrive_world(open_drive(), carla.OpendriveGenerationParameters(
            vertex_distance=.25, max_road_length=50, wall_height=0,
            additional_width=0, smooth_junctions=False,
            enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / FPS
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        survey = _survey(carla, mapping)
        _write_new(output / "native-map-survey.json", {
            "lane_readback": survey,
            "native_map_sha256": hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            "physical_speed_observed": False, "selected": False})
        library = world.get_blueprint_library()
        ego_bp = library.find("vehicle.tesla.model3")
        ego_bp.set_attribute("role_name", "c111294_speed_subject")
        ego = world.spawn_actor(ego_bp, carla.Transform(
            carla.Location(x=1.75, y=70, z=.5), carla.Rotation(yaw=-90)))
        owned.append(ego)
        other_bp = library.find("vehicle.tesla.model3")
        other_bp.set_attribute("role_name", "c111294_opposing_vehicle")
        other = world.spawn_actor(other_bp, carla.Transform(
            carla.Location(x=-1.75, y=-100, z=.5), carla.Rotation(yaw=90)))
        owned.append(other)
        # This seeds initial speed only. The captured 24 s uses observed
        # feedback and Native physics; actual speed must be measured later.
        ego.set_target_velocity(carla.Vector3D(x=0, y=-SPEED_MPH[case] * MPH_TO_MPS, z=0))
        other.set_target_velocity(carla.Vector3D(x=0, y=10, z=0))
        for spec in camera_plan():
            bp = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", spec["width"]),
                               ("image_size_y", spec["height"]),
                               ("fov", spec["fov_deg"]), ("sensor_tick", 0)):
                bp.set_attribute(key, str(value))
            x, y, z = spec["xyz_m"]
            transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                carla.Rotation(yaw=spec["yaw_deg"], pitch=spec["pitch_deg"]))
            sensor = world.spawn_actor(bp, transform,
                attach_to=ego if spec["attachment"] == "ego" else None)
            owned.append(sensor)
            queues[spec["name"]] = queue.Queue()
            sensor.listen(queues[spec["name"]].put)
            logs[spec["name"]] = (output / (spec["name"] + ".encoder.log")).open("x")
            encoders[spec["name"]] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", f"{spec['width']}x{spec['height']}", "-r", str(FPS),
                "-i", "pipe:0", "-an", "-c:v", "ffv1", "-level", "1",
                str(output / (spec["name"] + ".mkv"))],
                stdin=subprocess.PIPE, stderr=logs[spec["name"]])
        capture = PipelineCapture(client, ego, output, plan["case_id"],
                                  visibility=False,
                                  required_observations=config.get("required_atoms", []))
        (output / "channels").mkdir()
        for name in CHANNELS:
            channels[name] = (output / "channels" / (name + ".jsonl")).open("x")
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / "native_samples.jsonl").open("x") as native_file, \
             (output / "video_frames.jsonl").open("x") as video_file:
            for index in range(FRAMES):
                transform = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                command = control_command(speed, transform.location.x - 1.75,
                    transform.rotation.yaw + 90, SPEED_MPH[case], plan["knobs"])
                ego.apply_control(carla.VehicleControl(**command))
                other.set_target_velocity(carla.Vector3D(x=0, y=10, z=0))
                frame = world.tick()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds - start
                row = native_sample(index, frame, elapsed, ego, other)
                native_file.write(json.dumps(row, allow_nan=False) + "\n")
                capture.capture(frame, elapsed, extra={"c111294_speed_source": row})
                values = {"ego_pose": row["ego_position_m"],
                          "ego_speed": math.sqrt(sum(v*v for v in row["ego_velocity_mps"])),
                          "observed_speed": math.sqrt(sum(v*v for v in row["ego_velocity_mps"])) / MPH_TO_MPS,
                          "other_vehicle_pose": row["other_position_m"]}
                for name, stream in channels.items():
                    stream.write(json.dumps({"frame": index, "native_frame": frame,
                        "time_s": elapsed, "value": values[name]}, allow_nan=False) + "\n")
                for spec in camera_plan():
                    image = queues[spec["name"]].get(timeout=30)
                    while image.frame < frame:
                        image = queues[spec["name"]].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError("Original camera/Native frame join failed")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        spec["height"], spec["width"], 4)[:, :, :3][:, :, ::-1]
                    encoders[spec["name"]].stdin.write(rgb.tobytes())
                video_file.write(json.dumps({"video_frame": index, "native_frame": frame,
                    "carla_frame": frame, "time_s": elapsed}) + "\n")
                frames += 1
        if frames != FRAMES:
            raise RuntimeError("Original capture incomplete")
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        for stream in channels.values():
            stream.close()
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError("Lossless original camera encoder failed: " + name)
            except BaseException as exc:
                error = error or {"encoder_error": str(exc)}
            logs[name].close()
        if capture is not None:
            try:
                capture.close(confirmed=error is None)
                if error is None:
                    manifest_path = output / "capture/manifest.json"
                    manifest = json.loads(manifest_path.read_text())
                    for name in ("native_samples.jsonl", "video_frames.jsonl",
                                 *(spec["name"] + ".mkv" for spec in camera_plan())):
                        manifest["sources"][name] = _sha(output / name)
                    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
                    from measure_speed import measure
                    source = output / "native_samples.jsonl"
                    _write_new(output / "speed-measurement.json",
                               measure(source, _sha(source)))
            except BaseException as exc:
                error = error or {"capture_close_error": str(exc)}
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"actor_cleanup_error": str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {"world_restore_error": str(exc)}
        _write_new(output / "native-capture-report.json", {
            "case_id": plan["case_id"], "candidate_id": candidate,
            "frames": frames, "expected_frames": FRAMES,
            "restoration": restored, "error": error,
            "accepted": False, "legal_verdict": None})
    if error:
        raise RuntimeError("Native attempt failed; see native-capture-report.json")
    return {"case_id": plan["case_id"], "frames": frames,
            "accepted": False, "physical_speed_observed": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case", choices=sorted(SPEED_MPH))
    parser.add_argument("--candidate", choices=CANDIDATES)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    config_path = Path("config.json")
    if args.output_dir and (args.output_dir / "config.json").is_file():
        config_path = args.output_dir / "config.json"
    config = json.loads(config_path.read_text()) if config_path.is_file() else {}
    case = args.case or config.get("case_suffix")
    candidate = args.candidate or config.get("candidate_id")
    if args.check:
        rows = ([check(case, candidate)] if case and candidate else
                [check(c, v) for c in SPEED_MPH for v in CANDIDATES])
        print(json.dumps({"passed": True, "cpu_preflights": len(rows),
                          "native_capture_executed": False}, sort_keys=True))
    else:
        if not all((case, candidate, args.output_dir, args.host, args.port)):
            parser.error("Native capture requires exact config, output directory, host and port")
        print(json.dumps(execute(case, candidate, args.output_dir,
                                 args.host, args.port), sort_keys=True))
