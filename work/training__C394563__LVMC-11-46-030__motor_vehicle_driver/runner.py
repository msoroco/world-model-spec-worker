"""Prospective original Native school-warning capture; CARLA is imported lazily."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess

from school_native_plan import SchoolController, check_pair, plan
from school_warning_scene import scene_request, validate_request


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
REVIEW_FIELDS = ("school_lane_source_path", "child_identity_source_path",
                 "warning_asset_source_path", "municipal_jurisdiction_source_path")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    pair = check_pair()
    selected = json.loads(Path("selected-case.json").read_text())
    config = json.loads(Path("config.json").read_text())
    suffix = selected["suffix"]
    request = scene_request(suffix)
    validate_request(request)
    if selected["case_id"].split("__")[-1] != suffix:
        raise ValueError("Selected school-warning case identity differs")
    if len(plan(suffix)) != 600:
        raise ValueError("Exact request frame count differs")
    if config.get("controller_throttle_scale") not in (1.0, 0.8):
        raise ValueError("Unknown school-warning controller gain")
    return {"case_id": selected["case_id"], "request": suffix,
            "pair": pair, "controller_throttle_scale": config["controller_throttle_scale"],
            "original_native_observed": False}


def _review(output, library):
    supplied = os.environ.get("SCHOOL_LANE_REVIEW")
    if not supplied:
        raise ValueError("Supply source-reviewed school lane packet in SCHOOL_LANE_REVIEW")
    packet = Path(supplied).resolve()
    if not packet.is_file() or packet == output / "original-school-lane-review.json":
        raise ValueError("Original school lane and child source review missing")
    review = json.loads(packet.read_text())
    if review.get("school_pedestrian_lane_survey") is not True:
        raise ValueError("School pedestrian lane survey missing")
    for field in REVIEW_FIELDS:
        source = Path(review.get(field, ""))
        if not source.is_file() or not source.stat().st_size:
            raise ValueError("Original source file missing: " + field)
        if sha(source) != review.get(field.replace("_path", "_sha256")):
            raise ValueError("Original source hash differs: " + field)
    for key in ("lane_marker_blueprint", "warning_blueprint", "child_blueprint"):
        value = review.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError("Reviewed actor blueprint missing: " + key)
        library.find(value)
    if review.get("municipal_jurisdiction_reviewed") is not True:
        raise ValueError("Municipal jurisdiction source review missing")
    shutil.copyfile(packet, output / "original-school-lane-review.json")
    if sha(packet) != sha(output / "original-school-lane-review.json"):
        raise ValueError("Copied original school lane review differs")
    return review


def _camera(world, library, carla, spec, ego):
    blueprint = library.find("sensor.camera.rgb")
    blueprint.set_attribute("image_size_x", str(spec["width"]))
    blueprint.set_attribute("image_size_y", str(spec["height"]))
    blueprint.set_attribute("fov", str(spec["fov_deg"]))
    blueprint.set_attribute("sensor_tick", ".05")
    camera = next(item for item in scene_request("probe_1")["cameras"]
                  if item["name"] == spec["name"])
    x, y, z = camera["xyz"]
    transform = carla.Transform(carla.Location(x=x, y=y, z=z),
                                carla.Rotation(pitch=camera["pitch"], yaw=camera["yaw"]))
    if spec["name"] == "driver_reference":
        return world.spawn_actor(blueprint, transform, attach_to=ego)
    return world.spawn_actor(blueprint, transform)


def capture(output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    root = Path(__file__).resolve().parent
    selected = json.loads((root / "selected-case.json").read_text())
    config = json.loads((root / "config.json").read_text())
    suffix = selected["suffix"]
    request = scene_request(suffix)
    validate_request(request)
    rows = plan(suffix)
    output = Path(output_dir).resolve()
    if not output.is_dir() or (output / "native-rows.jsonl").exists():
        raise ValueError("Fresh Native attempt directory required")
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = snapshot(client)
    owned, encoders, streams = [], {}, {}
    pipeline = None
    changed = complete = False
    try:
        world = client.generate_opendrive_world(request["road_opendrive"])
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        (output / "road.xodr").write_text(world.get_map().to_opendrive())
        library = world.get_blueprint_library()
        review = _review(output, library)
        lane = world.spawn_actor(library.find(review["lane_marker_blueprint"]),
            carla.Transform(carla.Location(x=0, y=0, z=.05), carla.Rotation()))
        owned.append(lane)
        warning = world.spawn_actor(library.find(review["warning_blueprint"]),
            carla.Transform(carla.Location(x=-1, y=-6, z=1), carla.Rotation(yaw=90)))
        owned.append(warning)
        child = world.spawn_actor(library.find(review["child_blueprint"]),
            carla.Transform(carla.Location(x=-2, y=-8, z=.5), carla.Rotation(yaw=90)))
        owned.append(child)
        ego = world.spawn_actor(library.find(request["vehicle"]["blueprint"]),
            carla.Transform(carla.Location(x=-65, y=-1.75, z=1), carla.Rotation()))
        owned.append(ego)
        pipeline = PipelineCapture(client, ego, output, config["case_id"],
            visibility=False, required_observations=["kin.position", "kin.speed"])
        for spec in config["cameras"]:
            name = spec["name"]
            sensor = _camera(world, library, carla, spec, ego)
            owned.append(sensor)
            stream = queue.Queue()
            sensor.listen(stream.put)
            streams[name] = stream
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "bgra", "-s",
                f"{spec['width']}x{spec['height']}", "-r", "20", "-i", "-",
                "-frames:v", "600", "-c:v", "ffv1", "-level", "1",
                str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        controller = SchoolController(suffix)
        first_time = None
        with FrameMap(output / "video_frames.jsonl") as frame_map, \
                (output / "native-rows.jsonl").open("x") as stream:
            for index, request_row in enumerate(rows):
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                if index == 250:
                    warning.set_transform(carla.Transform(
                        carla.Location(x=-1, y=-6, z=-20), carla.Rotation(yaw=90)))
                warning_location = warning.get_location()
                observed_removal = warning_location.z < -10
                command = controller.step(index, pose.location.x, speed,
                    not observed_removal, "signal_removed" if observed_removal else None)
                ego.apply_control(carla.VehicleControl(
                    throttle=command["throttle"] * config["controller_throttle_scale"],
                    brake=command["brake"], steer=command["steer"]))
                native_frame = world.tick()
                snapshot = world.get_snapshot()
                if snapshot.frame != native_frame:
                    raise RuntimeError("Native snapshot frame differs")
                if first_time is None:
                    first_time = snapshot.timestamp.elapsed_seconds - .05
                time_s = (index + 1) / 20
                if abs(snapshot.timestamp.elapsed_seconds - first_time - time_s) > .001:
                    raise RuntimeError("Native 20 Hz time join differs")
                pipeline.capture(native_frame, time_s)
                camera_native = {}
                for name, sensor_stream in streams.items():
                    image = sensor_stream.get(timeout=30)
                    while image.frame < native_frame:
                        image = sensor_stream.get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError("Native camera frame join differs")
                    encoders[name].stdin.write(image.raw_data)
                    camera_native[name] = image.frame
                frame_map.append(native_frame, time_s,
                                 camera_native_frames=camera_native)
                current = ego.get_transform()
                velocity = ego.get_velocity()
                current_speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
                child_location = child.get_location()
                warning_location = warning.get_location()
                record = {"video_frame": index, "native_frame": native_frame,
                    "time_s": index / 20, "source_cameras": {name: index for name in CAMERAS},
                    "camera_native_frames": camera_native,
                    "vehicle_actor_id": ego.id, "vehicle_center_x_m": current.location.x,
                    "vehicle_center_y_m": current.location.y,
                    "vehicle_length_m": 2 * ego.bounding_box.extent.x,
                    "observed_speed_mps": current_speed,
                    "warning_actor_id": warning.id,
                    "warning_xyz_m": [warning_location.x, warning_location.y,
                                      warning_location.z],
                    "warning_role": "signal_device",
                    "warning_active": warning_location.z >= -10,
                    "child_actor_id": child.id,
                    "child_xyz_m": [child_location.x, child_location.y, child_location.z],
                    "children_about_to_cross_or_crossing":
                        child_location.x <= 4 and child_location.y <= -5,
                    "release_event": "signal_removed" if index == 250 and
                        warning_location.z < -10 else None,
                    "requested_target_center_x_m": request_row["target_center_x_m"],
                    "original_lane_and_child_review_pending": True}
                stream.write(json.dumps(record, allow_nan=False) + "\n")
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            if process.wait(timeout=180):
                raise RuntimeError("Original camera encoding failed: " + name +
                                   ": " + error.decode()[-300:])
        names = ["road.xodr", "native-rows.jsonl", "video_frames.jsonl",
                 "original-school-lane-review.json"] + [name + ".mkv" for name in CAMERAS]
        for field in REVIEW_FIELDS:
            source = Path(review[field])
            destination = output / ("review-" + field.removesuffix("_path"))
            shutil.copyfile(source, destination)
            names.append(destination.name)
        (output / "captured-source-hashes.json").write_text(json.dumps({
            "source_kind": "original_native_capture", "case_id": config["case_id"],
            "sha256": {name: sha(output / name) for name in names},
            "physical_or_legal_outcome_claimed": False}, indent=2) + "\n")
        complete = True
        return {"case_id": config["case_id"], "frames": 600,
                "physical_or_legal_outcome_claimed": False}
    finally:
        cleanup_error = None
        if pipeline is not None:
            try:
                pipeline.close(confirmed=complete)
            except Exception as error:
                cleanup_error = error
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
                actor.destroy()
            except Exception:
                pass
        restoration = restore(client, prior) if changed else {"restored": True}
        if complete:
            seal_capture(output, frames=600, restoration=restoration, errors=[],
                encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                context={"case_id": config["case_id"],
                         "original_school_lane_and_child_review": "pending"})
        if cleanup_error is not None:
            raise cleanup_error


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    elif args.output_dir:
        print(json.dumps(capture(args.output_dir, args.host, args.port)))
    else:
        parser.error("Supply --check or a dedicated Native attempt directory")
