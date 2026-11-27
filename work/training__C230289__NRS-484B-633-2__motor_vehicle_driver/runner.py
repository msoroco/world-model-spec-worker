"""Source-gated selected surveyed-bridge Native construction for C230289.

Administrative declaration and sign status must come from an original survey.
Requested controller speed and observed Native velocity are distinct.
"""
import argparse
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = "training__C230289__NRS-484B-633-2__motor_vehicle_driver"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(config):
    require(config["case_id"] in {ASSIGNMENT + "__probe_01", ASSIGNMENT + "__probe_02"} and config["law_id"] == "NRS-484B-633-2"
            and config["cell_id"] == "C230289" and config["actor"] == "motor_vehicle_driver",
            "exact assignment changed")
    require(config["frozen_cell"] == {"layout": "road", "maneuver": "travel",
                                      "control": "speed_limit_sign"}, "frozen cell changed")
    require(config["status"] == "selected_cpu_prepared"
            and not config.get("physical_completion") and config["legal_verdict"] is None,
            "unproved outcome claimed")
    require(config["rate_hz"] == 20 and config["duration_s"] == 30 and config["frames"] == 600,
            "30-second capture missing")
    require(config["requested_offset_from_declared_maximum_mph"] == (-10 if config["case_id"].endswith("probe_01") else 10),
            "speed request changed")
    require(tuple(c["name"] for c in config["cameras"]) == VIEWS
            and all(c["fps"] == 20 and c["width"] >= 1280 and c["height"] >= 720
                    for c in config["cameras"]), "four-camera source plan incomplete")
    return {"case_id": config["case_id"], "frame_count": 600, "views": list(VIEWS),
            "carla_contacted": False, "selected": True, "measured_speed_mph": None}


def read_survey(path):
    survey = json.loads(Path(path).read_text())
    require(survey.get("assignment_id") == ASSIGNMENT and survey.get("source_kind") == "original_native_bridge_survey",
            "original assignment bridge survey required")
    require(survey.get("map_name") and survey.get("highway_source_id")
            and survey.get("structure_source_id") and survey.get("chapter_408_source_id")
            and survey.get("structure_type") in {"bridge", "other_elevated_structure"},
            "highway bridge geometry provenance missing")
    require(survey.get("fixed_cell") == {"layout": "road", "maneuver": "travel",
                                         "control": "speed_limit_sign"}, "survey cell mismatch")
    admin = survey.get("administrative_declaration", {})
    require(all(admin.get(key) for key in ("department_source_id", "investigation_source_id",
                                         "finding_source_id", "declaration_source_id",
                                         "otherwise_permissible_speed_source_id")),
            "administrative declaration provenance missing")
    maximum = admin.get("safe_maximum_mph")
    ordinary = admin.get("otherwise_permissible_speed_mph")
    require(isinstance(maximum, (int, float)) and math.isfinite(maximum) and maximum > 10
            and isinstance(ordinary, (int, float)) and math.isfinite(ordinary)
            and ordinary > maximum,
            "declared structural maximum must be below sourced otherwise permissible speed")
    signs = survey.get("signs", [])
    require(len(signs) == 2 and {s.get("end") for s in signs} == {"first", "second"}
            and all(s.get("source_id") and s.get("visible_instruction_source_id")
                    and s.get("department_authorization_source_id") and s.get("maintained_source_id")
                    and s.get("instruction_kind") == "structure_maximum"
                    and s.get("maximum_mph") == maximum and s.get("distance_before_end_ft") == 100
                    and s.get("governed_approach_source_id") and len(s.get("position_xyz_m", [])) == 3
                    and len(s.get("structure_end_xyz_m", [])) == 3 for s in signs),
            "two authorized 100-foot structural signs missing")
    require(all(abs(math.dist(s["position_xyz_m"], s["structure_end_xyz_m"]) * 3.280839895 - 100) <= 2 for s in signs),
            "structural sign coordinates do not support 100-foot distance")
    require(len(survey.get("spawn_xyz_yaw_deg", [])) == 4
            and len(survey.get("bridge_exit_xyz_m", [])) == 3
            and survey.get("vehicle_blueprint"), "surveyed Native route missing")
    polygon = survey.get("structure_polygon_xy_m", [])
    require(len(polygon) >= 3 and all(len(v) == 2 and all(isinstance(c, (int, float)) and math.isfinite(c) for c in v) for v in polygon),
            "surveyed structure footprint missing")
    return survey


def inside_polygon(x, y, vertices):
    inside = False
    j = len(vertices) - 1
    for i, (xi, yi) in enumerate(vertices):
        xj, yj = vertices[j]
        if ((yi > y) != (yj > y)) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def execute(config, output_dir, survey_path, host, port):
    check(config)
    require(survey_path, "original assignment bridge survey required")
    survey = read_survey(survey_path)
    require(".runtime-work" in os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""),
            "set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    repo = ROOT.parents[1]
    sys.path.insert(0, str(repo / "runtime" / "scenario_pipeline"))
    sys.path.insert(1, str(repo / "runtime" / "python"))
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot

    output = Path(output_dir)
    require(output.is_dir(), "materialized output directory required")
    (output / "original_bridge_survey.json").write_bytes(Path(survey_path).read_bytes())
    client = carla.Client(host, port)
    client.set_timeout(15)
    world = client.get_world()
    original = snapshot(client)
    actors, sensors, encoders, codes = [], [], {}, {}
    completed = False
    images = queue.Queue()
    try:
        require(world.get_map().name == survey["map_name"], "survey map differs")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        library = world.get_blueprint_library()
        bp = library.find(survey["vehicle_blueprint"])
        require(bp is not None, "vehicle blueprint unavailable")
        x, y, z, yaw = survey["spawn_xyz_yaw_deg"]
        vehicle = world.try_spawn_actor(bp, carla.Transform(carla.Location(x=x, y=y, z=z),
                                           carla.Rotation(yaw=yaw)))
        require(vehicle is not None, "surveyed spawn occupied")
        actors.append(vehicle)
        for camera in config["cameras"]:
            camera_bp = library.find("sensor.camera.rgb")
            camera_bp.set_attribute("image_size_x", str(camera["width"]))
            camera_bp.set_attribute("image_size_y", str(camera["height"]))
            camera_bp.set_attribute("fov", str(camera["fov_deg"]))
            cx, cy, cz = camera["location_xyz_m"]
            pitch, cyaw, roll = camera["rotation_pyr_deg"]
            sensor = world.spawn_actor(camera_bp, carla.Transform(carla.Location(x=cx, y=cy, z=cz),
                                       carla.Rotation(pitch=pitch, yaw=cyaw, roll=roll)), attach_to=vehicle)
            actors.append(sensor)
            sensors.append(sensor)
            encoders[camera["name"]] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "bgra",
                "-s", f"{camera['width']}x{camera['height']}", "-r", "20", "-i", "-",
                "-frames:v", "600", "-c:v", "ffv1", "-level", "1",
                str(output / (camera["name"] + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            sensor.listen(lambda image, name=camera["name"]: images.put((name, image)))
        with PipelineCapture(client, vehicle, output, config["case_id"], required_observations=config["required_atoms"]) as capture, \
                FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "bridge-native.jsonl").open("x", buffering=1) as trace:
            target_speed_mps = (survey["administrative_declaration"]["safe_maximum_mph"] + config["requested_offset_from_declared_maximum_mph"]) / 2.2369362920544
            for frame in range(600):
                pose, velocity = vehicle.get_transform(), vehicle.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                target = survey["bridge_exit_xyz_m"]
                heading = math.atan2(target[1] - pose.location.y, target[0] - pose.location.x)
                relative = math.atan2(math.sin(heading - math.radians(pose.rotation.yaw)),
                                      math.cos(heading - math.radians(pose.rotation.yaw)))
                steer = max(-0.35, min(0.35, relative))
                throttle, brake = (0.55, 0.0) if speed < target_speed_mps else (0.0, 0.1)
                vehicle.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
                native_frame = world.tick()
                observed_pose, observed_velocity = vehicle.get_transform(), vehicle.get_velocity()
                seen = set()
                while len(seen) < 4:
                    name, image = images.get(timeout=15)
                    if image.frame != native_frame or name in seen:
                        continue
                    encoders[name].stdin.write(image.raw_data)
                    seen.add(name)
                capture.capture(native_frame, frame / 20, extra={"video_frame": frame})
                frame_map.append(native_frame, frame / 20,
                                 native_elapsed_s=world.get_snapshot().timestamp.elapsed_seconds)
                trace.write(json.dumps({"source_kind": "original_native_observation", "frame": frame,
                                        "native_frame": native_frame, "t_s": frame / 20,
                                        "vehicle_id": vehicle.id, "structure_source_id": survey["structure_source_id"],
                                        "position_xyz_m": [observed_pose.location.x, observed_pose.location.y,
                                                           observed_pose.location.z],
                                        "velocity_xyz_mps": [observed_velocity.x, observed_velocity.y,
                                                             observed_velocity.z],
                                        "requested_speed_mph": survey["administrative_declaration"]["safe_maximum_mph"] + config["requested_offset_from_declared_maximum_mph"],
                                        "on_structure_verified": inside_polygon(observed_pose.location.x, observed_pose.location.y, survey["structure_polygon_xy_m"]),
                                        "structure_occupancy_source": survey["structure_source_id"]}) + "\n")
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            codes[name] = process.wait(timeout=180)
            require(codes[name] == 0 and (output / (name + ".mkv")).is_file(),
                    "Source camera encode failed: " + name + " " + error.decode()[-200:])
        completed = True
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
        if completed and len(codes) == 4:
            seal_capture(output, frames=600, restoration=restored, errors=[],
                         encoder_exit_codes=codes,
                         context={"case_id": config["case_id"], "source_review": "pending"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--bridge-survey")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text())
    if args.check:
        print(json.dumps(check(config)))
    else:
        require(args.output_dir, "output directory required")
        execute(config, args.output_dir, args.bridge_survey or os.environ.get("SCENARIO_BRIDGE_SURVEY"),
                args.host, args.port)
