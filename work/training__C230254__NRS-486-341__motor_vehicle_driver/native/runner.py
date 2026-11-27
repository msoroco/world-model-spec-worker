"""Original Native two-vehicle lane-use acquisition; no legal verdict."""

import argparse
import json
import math
import os
import queue
import subprocess
from pathlib import Path

from acquire_lane_use import append_source, sample

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
LAW = "NRS-486-341"
CELL = "C230254"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(config):
    require(config.get("law_id") == LAW and config.get("cell_id") == CELL
            and config.get("actor") == "motor_vehicle_driver", "Wrong frozen identity")
    require(config.get("frozen_cell") == {"layout": "road", "maneuver": "travel",
                                          "control": "motorcycle"}, "Frozen cell changed")
    require(config.get("selected_case_id") == config.get("case_id"), "Exact case differs")
    require(config.get("requested_setting") in ("full_lane_available", "blocked_by_ego"),
            "Unknown exact setting")
    require(config.get("rate_hz") == 20 and config.get("duration_s") == 30
            and config.get("frames") == 600, "Full capture window required")
    cameras = config.get("cameras")
    require(isinstance(cameras, list) and tuple(c["name"] for c in cameras) == VIEWS,
            "Four source cameras required")
    for camera in cameras:
        require(camera["fps"] == 20 and camera["width"] >= 1280
                and camera["height"] >= 720 and camera["fov_deg"] > 0
                and len(camera["location_xyz_m"]) == 3
                and len(camera["rotation_pyr_deg"]) == 3,
                "Camera plan incomplete")
    require(config.get("legal_verdict") is None and config.get("physical_completion") == {},
            "Unverified outcome may not be claimed")
    return {"case_id": config["case_id"], "frames": 600,
            "views": list(VIEWS), "carla_contacted": False}


def _transform(carla, source):
    x, y, z = source["xyz_m"]
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(yaw=source["yaw_deg"]))


def read_survey(path, config):
    source = Path(path)
    survey = json.loads(source.read_text())
    require(survey.get("source_kind") == "original_native_context_survey"
            and survey.get("map_name") and survey.get("protected_vehicle_class") == "motorcycle",
            "Original motorcycle and map context survey required")
    for name in ("protected_spawn",):
        pose = survey.get(name)
        require(isinstance(pose, dict) and len(pose.get("xyz_m", [])) == 3
                and isinstance(pose.get("yaw_deg"), (int, float)),
                "Original actor spawn survey missing: " + name)
    require(survey.get("case_id") == config["case_id"], "Survey case differs")
    return survey, source.read_bytes()


def subject_transform(carla, protected_spawn, lateral_offset_m, behind_m):
    """Place the subject relative to the same protected route in both cases."""
    require(lateral_offset_m > 0 and behind_m >= 0, "Subject engineering offsets invalid")
    yaw = math.radians(protected_spawn["yaw_deg"])
    x, y, z = protected_spawn["xyz_m"]
    return carla.Transform(carla.Location(
        x=x - behind_m * math.cos(yaw) - lateral_offset_m * math.sin(yaw),
        y=y - behind_m * math.sin(yaw) + lateral_offset_m * math.cos(yaw), z=z),
        carla.Rotation(yaw=protected_spawn["yaw_deg"]))


def execute(config, destination, host, port):
    check(config)
    survey_path = os.environ.get("SCENARIO_CONTEXT_SURVEY")
    require(survey_path, "SCENARIO_CONTEXT_SURVEY is required")
    survey, survey_bytes = read_survey(survey_path, config)
    output = Path(destination).resolve()
    require(output.is_dir(), "Runtime must materialize the attempt directory")
    # The runtime resolver reads this at import time. Keep any generated paths
    # inside the dedicated attempt instead of the source checkout.
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(output)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.saved_processing import record_native_exit
    from worker_exchange.world_restore import restore, snapshot

    with (output / "lane-use-context.json").open("xb") as source:
        source.write(survey_bytes)
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original = snapshot(client)
    actors, sensors, encoders, codes = [], [], {}, {}
    images = queue.Queue()
    complete = False
    try:
        require(world.get_map().name == survey["map_name"], "Original map differs from survey")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library()
        protected = world.try_spawn_actor(blueprints.find(config["protected_blueprint"]),
                                          _transform(carla, survey["protected_spawn"]))
        require(protected is not None, "Protected motorcycle spawn failed")
        actors.append(protected)
        ego = world.try_spawn_actor(blueprints.find(config["subject_blueprint"]),
                                    subject_transform(carla, survey["protected_spawn"],
                                                      config["subject_lateral_offset_m"],
                                                      config["subject_behind_m"]))
        require(ego is not None, "Subject spawn failed")
        actors.append(ego)
        require(ego.id != protected.id, "Subject and protected actor are identical")
        for camera in config["cameras"]:
            name = camera["name"]
            bp = blueprints.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(camera["width"]))
            bp.set_attribute("image_size_y", str(camera["height"]))
            bp.set_attribute("fov", str(camera["fov_deg"]))
            cx, cy, cz = camera["location_xyz_m"]
            pitch, yaw, roll = camera["rotation_pyr_deg"]
            sensor = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=cx, y=cy, z=cz),
                carla.Rotation(pitch=pitch, yaw=yaw, roll=roll)), attach_to=ego)
            actors.append(sensor)
            sensors.append(sensor)
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "bgra",
                "-s", f"{camera['width']}x{camera['height']}", "-r", "20", "-i", "-",
                "-frames:v", "600", "-c:v", "ffv1", "-level", "1",
                str(output / (name + ".mkv"))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
            sensor.listen(lambda image, view=name: images.put((view, image)))
        refs = {"actor_trace": "trace.jsonl", "actor_bounds": "lane-use-source.jsonl",
                "lane_map": "lane-use-source.jsonl"}
        with PipelineCapture(client, ego, output, config["case_id"],
                             required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map:
            for index in range(config["frames"]):
                ego.apply_control(carla.VehicleControl(
                    throttle=config["subject_throttle"], steer=config["subject_steer"], brake=0))
                protected.apply_control(carla.VehicleControl(
                    throttle=config["protected_throttle"], steer=0, brake=0))
                native_frame = world.tick()
                seen = set()
                while len(seen) < len(VIEWS):
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    encoders[name].stdin.write(image.raw_data)
                    seen.add(name)
                elapsed = index / config["rate_hz"]
                capture.capture(native_frame, elapsed, extra={
                    "video_frame": index, "protected_actor_id": protected.id})
                frame_map.append(native_frame, elapsed,
                                 camera_native_frames={name: native_frame for name in VIEWS},
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                append_source(output / "lane-use-source.jsonl",
                              sample(world.get_map(), ego, protected,
                                     frame=index, native_frame=native_frame,
                                     time_s=elapsed, source_refs=refs))
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            codes[name] = process.wait(timeout=180)
            require(codes[name] == 0 and (output / (name + ".mkv")).is_file(),
                    "Original camera encode failed: " + name + " " + error.decode()[-200:])
        complete = True
    finally:
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for sensor in sensors:
            sensor.stop()
        for actor in reversed(actors):
            actor.destroy()
        restored = restore(client, original)
        if complete:
            seal_capture(output, frames=config["frames"], restoration=restored,
                         errors=[], encoder_exit_codes=codes,
                         context={"case_id": config["case_id"],
                                  "protected_actor_id": protected.id})
            record_native_exit(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        require(args.output_dir, "Original output directory required")
        execute(config, args.output_dir, args.host, args.port)
