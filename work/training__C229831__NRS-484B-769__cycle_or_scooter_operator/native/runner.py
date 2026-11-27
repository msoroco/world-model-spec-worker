"""Prospective original Native rider-arm capture for exact C229831 probes.

The CPU --check path imports no CARLA. A local GPU run must review actor
mounting, road geometry, arm pose and original pixels before acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import queue
import subprocess
import traceback
import xml.etree.ElementTree as ET

from rider_arm import request_rider, sample_rider, spawn_rider
from road import lane_center_route, open_drive
from route_control import apply as apply_route


AID = "training__C229831__NRS-484B-769__cycle_or_scooter_operator"
CASES = {AID + "__probe_a": "right_horizontal",
         AID + "__probe_b": "none",
         AID + "__probe_c": "left_upward"}
CAMERAS = (
    ("overview", 1920, 1080, [-11, -11, 24], 45, -60),
    ("approach", 1280, 720, [-28, 7, 5], -35, -12),
    ("reference_corner", 1280, 720, [4, 3, 7], -145, -25),
    ("driver_reference", 1280, 720, [-38, -1, 3], 0, -6),
)


def check(case_id):
    if case_id not in CASES:
        raise ValueError("Unknown exact rider-arm case")
    root = ET.fromstring(open_drive())
    if len(root.findall("road")) != 3 or len(root.findall("junction/connection")) != 1:
        raise ValueError("Authored connected right turn missing")
    if len(lane_center_route()) < 300 or len(CAMERAS) != 4:
        raise ValueError("Route or four-view capture plan missing")
    return {"case_id": case_id, "frames": 600, "rate_hz": 20,
            "camera_names": [camera[0] for camera in CAMERAS],
            "native_imported": False, "physical_acceptance_claimed": False}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _camera_pose(carla, xyz, yaw, pitch):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(yaw=yaw, pitch=pitch))


def _map_readback(carla, mapping):
    result = {}
    for name, xyz, road in (("approach", (-40, -1.75, 0.5), 1),
                            ("turn_arc", (-3.29, -3.29, 0.5), 13),
                            ("departure", (-1.75, -20, 0.5), 2)):
        waypoint = mapping.get_waypoint(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                                        project_to_road=False, lane_type=carla.LaneType.Driving)
        if waypoint is None or waypoint.road_id != road or waypoint.lane_id != -1:
            raise ValueError("Native right-turn lane readback failed: " + name)
        result[name] = {"road_id": waypoint.road_id, "lane_id": waypoint.lane_id,
                        "lane_width_m": waypoint.lane_width,
                        "center_xyz_m": [waypoint.transform.location.x,
                                         waypoint.transform.location.y,
                                         waypoint.transform.location.z]}
    return result


def execute(case_id, output, *, host="127.0.0.1", port=2000,
            walker_blueprint="walker.pedestrian.0001"):
    check(case_id)
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    if not output.is_dir() or not all((output / name).is_file()
                                      for name in ("config.json", "runner.py", "construction.json")):
        raise ValueError("Use a fresh materialized exact case directory")
    if any((output / name).exists() for name in ("road.xodr", "capture-seal.json",
                                               "rider_arm.jsonl", "camera_frames.jsonl")):
        raise ValueError("Original Native attempt already contains sources")
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old_world = client.get_world()
    if saved["settings"].synchronous_mode or any(actor.type_id.startswith(
            ("vehicle.", "walker.", "sensor.")) for actor in old_world.get_actors()):
        raise RuntimeError("Exclusive idle Native world required")
    owned, encoders, camera_queues = [], {}, {}
    capture = None
    changed = False
    error = None
    restoration = None
    frames = 0
    encoder_codes = {}
    try:
        road_text = open_drive()
        (output / "road.xodr").write_text(road_text)
        world = client.generate_opendrive_world(road_text,
            carla.OpendriveGenerationParameters(vertex_distance=.25,
                max_road_length=50, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        map_readback = _map_readback(carla, mapping)
        _write_new(output / "map_readback.json", map_readback)
        library = world.get_blueprint_library()
        bicycle_bp = library.find("vehicle.bh.crossbike")
        bicycle_bp.set_attribute("role_name", "c229831_signal_bicycle")
        bicycle = world.try_spawn_actor(bicycle_bp,
            _camera_pose(carla, [-45, -1.75, 0.8], 0, 0))
        if bicycle is None:
            raise RuntimeError("Original selected bicycle spawn failed")
        owned.append(bicycle)
        rider = spawn_rider(world, carla, bicycle, walker_blueprint)
        owned.append(rider)
        for name, width, height, xyz, yaw, pitch in CAMERAS:
            blueprint = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("sensor_tick", .05)):
                blueprint.set_attribute(key, str(value))
            sensor = world.spawn_actor(blueprint,
                                       _camera_pose(carla, xyz, yaw, pitch))
            owned.append(sensor)
            camera_queues[name] = queue.Queue()
            sensor.listen(camera_queues[name].put)
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-v", "error", "-n", "-f", "rawvideo",
                "-pix_fmt", "bgra", "-s", f"{width}x{height}", "-r", "20",
                "-i", "pipe:0", "-frames:v", "600", "-c:v", "ffv1",
                str(output / (name + ".mkv"))], stdin=subprocess.PIPE,
                stderr=subprocess.PIPE)
        capture = PipelineCapture(client, bicycle, output, case_id,
                                  visibility=False, required_observations=[])
        first_time = None
        prior_route_index = 0
        with FrameMap(output / "video_frames.jsonl") as frame_map, \
             (output / "rider_arm.jsonl").open("x") as arm_stream, \
             (output / "camera_frames.jsonl").open("x") as camera_stream:
            for index in range(600):
                route_row = apply_route(bicycle, carla,
                                        prior_index=prior_route_index)
                prior_route_index = route_row["route_index"]
                method = CASES[case_id] if 100 <= index < 140 else "none"
                request = request_rider(carla, bicycle, rider, method=method)
                native_frame = world.tick()
                snapshot_now = world.get_snapshot()
                if snapshot_now.frame != native_frame:
                    raise RuntimeError("Original Native tick identity differs")
                if first_time is None:
                    first_time = snapshot_now.timestamp.elapsed_seconds
                elapsed = snapshot_now.timestamp.elapsed_seconds - first_time
                sample = sample_rider(bicycle, rider, request=request, frame=index)
                sample["native_frame"] = native_frame
                sample["route_controller"] = route_row
                arm_stream.write(json.dumps(sample, allow_nan=False) + "\n")
                capture.capture(native_frame, elapsed, extra={"rider_arm": sample})
                camera_native_frames = {}
                pixel_source_ids = {}
                for name, width, height, *_ in CAMERAS:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = camera_queues[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError("Original camera/Native frame join failed")
                    encoders[name].stdin.write(image.raw_data)
                    camera_native_frames[name] = image.frame
                    pixel_source_ids[name] = name + ".mkv#frame=" + str(index)
                frame_map.append(native_frame, elapsed,
                                 camera_native_frames=camera_native_frames)
                camera_stream.write(json.dumps({
                    "frame": index, "time_s": index / 20,
                    "camera_names": sorted(camera_native_frames),
                    "pixel_source_ids": pixel_source_ids,
                    "native_frame": native_frame}, allow_nan=False) + "\n")
                frames += 1
        route = lane_center_route()
        _write_new(output / "road_context.json", {
            "source_kind": "original_native_map_and_capture",
            "machine_class": "bicycle",
            "machine_class_source_id": str(bicycle.type_id) + ":" + str(bicycle.id),
            "rider_actor_id": rider.id, "bicycle_actor_id": bicycle.id,
            "rider_mount_source_id": "original_rider_actor:" + str(rider.id),
            "rider_arm_source_id": "rider_arm.jsonl",
            "camera_calibration_source_id": "four_original_camera_transforms",
            "roadway_polygon_source_id": "road.xodr+map_readback.json",
            "right_turn_route_source_id": "road.xodr+map_readback.json",
            "roadway_polygon_xy_m": [[-60, -3.5], [-7, -3.5],
                                      [-3.5, -7], [-3.5, -60],
                                      [0, -60], [0, 0], [-60, 0]],
            "right_turn_route_xy_m": route,
            "map_readback_sha256": _sha(output / "map_readback.json"),
            "authored_road_sha256": _sha(output / "road.xodr"),
            "physical_roadway_status_verified": False,
            "physical_mount_verified": False,
            "original_pixels_reviewed": False,
        })
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
                encoder_codes[name] = encoder.wait(timeout=180)
                if encoder_codes[name]:
                    error = error or {"encoder_failure": name}
            except BaseException as exc:
                error = error or {"encoder_close_error": str(exc)}
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"owned_actor_cleanup_error": str(exc)}
        if changed:
            try:
                restoration = restore(client, saved)
            except BaseException as exc:
                error = error or {"world_restore_error": str(exc)}
        _write_new(output / "native-capture-report.json", {
            "case_id": case_id, "frames": frames, "expected_frames": 600,
            "restoration": restoration, "encoder_exit_codes": encoder_codes,
            "error": error, "physical_acceptance_claimed": False})
    if error:
        raise RuntimeError("Original Native capture failed: " + str(error))
    seal_capture(output, frames=frames, restoration=restoration, errors=[],
                 encoder_exit_codes=encoder_codes,
                 context={"case_id": case_id, "physical_acceptance_claimed": False})
    return {"case_id": case_id, "original_frames": frames,
            "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case", choices=sorted(CASES), required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--walker-blueprint", default="walker.pedestrian.0001")
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(args.case), sort_keys=True))
    else:
        if args.output_dir is None:
            parser.error("--output-dir required for Native capture")
        print(json.dumps(execute(args.case, args.output_dir, host=args.host,
                                 port=args.port, walker_blueprint=args.walker_blueprint)))
