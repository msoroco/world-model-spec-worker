"""Source-gated original pedestrian/vehicle and four-view CARLA acquisition.

The reviewed packet is supplied locally at capture time. It names an original
OpenDRIVE source, exact routes and camera poses. No fixture is a site review.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from queue import Empty, Queue
import shutil
import subprocess

from road_geometry import Route, pedestrian_faces_approach, side_of_highway
from site_source import load_reviewed_site

CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def reviewed_route(packet: dict, case_id: str, spec: dict) -> dict:
    routes = packet.get("routes")
    if not isinstance(routes, dict) or case_id not in routes:
        raise ValueError("reviewed original exact-case route missing")
    route = routes[case_id]
    if not isinstance(route, dict) or any(key not in route for key in (
            "pedestrian_start_xyz_m", "pedestrian_end_xyz_m", "vehicle_start_xyz_m",
            "vehicle_end_xyz_m", "walker_speed_mps", "vehicle_speed_mps")):
        raise ValueError("reviewed original route fields missing")
    for key in ("pedestrian_start_xyz_m", "pedestrian_end_xyz_m", "vehicle_start_xyz_m", "vehicle_end_xyz_m"):
        xyz = route[key]
        if not isinstance(xyz, list) or len(xyz) != 3 or not all(type(x) in (int, float) and math.isfinite(x) for x in xyz):
            raise ValueError("reviewed original route coordinate missing: " + key)
    if not (0.3 <= route["walker_speed_mps"] <= 1.5 and 1 <= route["vehicle_speed_mps"] <= 10):
        raise ValueError("reviewed original bounded controller targets missing")
    vehicle = Route(tuple(route["vehicle_start_xyz_m"][:2]), tuple(route["vehicle_end_xyz_m"][:2]))
    pedestrian = Route(tuple(route["pedestrian_start_xyz_m"][:2]), tuple(route["pedestrian_end_xyz_m"][:2]))
    faces = pedestrian_faces_approach(vehicle, pedestrian)
    if faces != (spec["pedestrian_heading"] == "facing"):
        raise ValueError("reviewed original pedestrian heading comparison differs")
    observed = side_of_highway(vehicle, pedestrian.start)
    intended = "traffic_right" if spec["pedestrian_highway_side"] == "left" else "traffic_left"
    if observed != intended:
        raise ValueError("reviewed original highway-side comparison differs")
    expected_direction = "east" if vehicle.unit[0] > 0 else "west"
    if expected_direction != spec["approach_direction"]:
        raise ValueError("reviewed original approach direction differs")
    return route


def camera_poses(packet: dict, case_id: str) -> dict:
    poses = packet.get("cameras", {}).get(case_id)
    if not isinstance(poses, dict) or set(poses) != set(CAMERAS):
        raise ValueError("reviewed four-camera poses missing")
    for name, pose in poses.items():
        if not isinstance(pose, dict) or any(not isinstance(pose.get(key), list) or len(pose[key]) != 3 or
                not all(type(x) in (int, float) and math.isfinite(x) for x in pose[key])
                for key in ("location_xyz_m", "pitch_yaw_roll_deg")):
            raise ValueError("reviewed camera pose missing: " + name)
    return poses


def _spawn_camera(world, carla, pose: dict, name: str, queue: Queue):
    width, height = CAMERAS[name]
    blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
    blueprint.set_attribute("image_size_x", str(width))
    blueprint.set_attribute("image_size_y", str(height))
    blueprint.set_attribute("sensor_tick", "0.05")
    xyz, pyr = pose["location_xyz_m"], pose["pitch_yaw_roll_deg"]
    actor = world.try_spawn_actor(blueprint, carla.Transform(carla.Location(*xyz),
        carla.Rotation(pitch=pyr[0], yaw=pyr[1], roll=pyr[2])))
    if actor is None:
        raise RuntimeError("original walking camera spawn failed: " + name)
    actor.listen(lambda image: queue.put(image))
    return actor


def _encoder(path: Path, width: int, height: int):
    return subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
        "-framerate", "20", "-i", "pipe:0", "-c:v", "ffv1", str(path)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _frame(queue: Queue, expected: int):
    try:
        image = queue.get(timeout=15)
    except Empty as error:
        raise RuntimeError("synchronized walking camera frame missing") from error
    if image.frame != expected:
        raise ValueError("original walking camera frame identity differs")
    return image


def _transform(actor) -> tuple[list[float], list[float]]:
    transform = actor.get_transform()
    forward = transform.get_forward_vector()
    loc = transform.location
    return [float(loc.x), float(loc.y), float(loc.z)], [float(forward.x), float(forward.y)]


def retain_review(review_path: Path, packet: dict, output: Path) -> dict:
    root = output / "reviewed-site"
    root.mkdir(exist_ok=False)
    shutil.copy2(review_path, root / "packet.json")
    sources = {}
    for key in ("public_highway_source", "public_access_source", "highway_boundaries_source",
                "sidewalk_inventory_source", "subsection_6_review_source", "opendrive_source"):
        original = review_path.parent / packet[key]["path"]
        dest = root / (key + original.suffix)
        shutil.copy2(original, dest)
        sources[key] = {"path": str(dest.relative_to(output)), "sha256": sha(dest)}
    receipt = {"packet": {"path": "reviewed-site/packet.json", "sha256": sha(root / "packet.json")},
               "sources": sources, "reviewer": packet["reviewer"]}
    write(output / "reviewed-site-receipt.json", receipt)
    return receipt


def run_native(review_path: Path, case_id: str, spec: dict, output_dir: Path,
               *, walker_speed_mps: float, host: str = "127.0.0.1", port: int = 2000) -> dict:
    output = Path(output_dir).resolve()
    if not output.is_dir() or any((output / name).exists() for name in (
            "trace.jsonl", "video_frames.jsonl", "original-walking-observations.json",
            "original-walking-receipt.json", "result.json")):
        raise ValueError("fresh materialized walking attempt directory required")
    review_path = Path(review_path).resolve()
    packet = load_reviewed_site(review_path)
    route = reviewed_route(packet, case_id, spec)
    poses = camera_poses(packet, case_id)
    opendrive = (review_path.parent / packet["opendrive_source"]["path"]).read_text(encoding="utf-8")
    retain_review(review_path, packet, output)
    if "SCENARIO_PIPELINE_OUTPUT_ROOT" not in os.environ:
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(output.parent / "pipeline-output")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    client = carla.Client(host, port)
    client.set_timeout(30)
    prior = snapshot(client)
    actors, cameras, queues, encoders = [], {}, {}, {}
    capture = None
    frame_map = None
    failure = None
    restored = False
    try:
        world = client.generate_opendrive_world(opendrive)
        if hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() != packet["map_sha256"]:
            raise ValueError("reviewed original Native map readback differs")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library()
        vehicle_bp = next(iter(blueprints.filter("vehicle.*")), None)
        walker_bp = next(iter(blueprints.filter("walker.pedestrian.*")), None)
        if vehicle_bp is None or walker_bp is None:
            raise RuntimeError("vehicle or pedestrian blueprint unavailable")
        vx, vy = Route(tuple(route["vehicle_start_xyz_m"][:2]), tuple(route["vehicle_end_xyz_m"][:2])).unit
        px, py = Route(tuple(route["pedestrian_start_xyz_m"][:2]), tuple(route["pedestrian_end_xyz_m"][:2])).unit
        vehicle = world.try_spawn_actor(vehicle_bp, carla.Transform(
            carla.Location(*route["vehicle_start_xyz_m"]), carla.Rotation(yaw=math.degrees(math.atan2(vy, vx)))))
        if vehicle is None:
            raise RuntimeError("approaching vehicle spawn failed")
        actors.append(vehicle)
        walker = world.try_spawn_actor(walker_bp, carla.Transform(
            carla.Location(*route["pedestrian_start_xyz_m"]), carla.Rotation(yaw=math.degrees(math.atan2(py, px)))))
        if walker is None:
            raise RuntimeError("pedestrian spawn failed")
        actors.append(walker)
        capture = PipelineCapture(client, vehicle, output, case_id)
        for name, dimensions in CAMERAS.items():
            queues[name] = Queue()
            cameras[name] = _spawn_camera(world, carla, poses[name], name, queues[name])
            encoders[name] = _encoder(output / (name + ".mkv"), *dimensions)
        frame_map = FrameMap(output / "video_frames.jsonl")
        observations = []
        for _ in range(900):
            walker.apply_control(carla.WalkerControl(carla.Vector3D(px, py, 0), float(walker_speed_mps), False))
            vehicle.set_target_velocity(carla.Vector3D(vx * route["vehicle_speed_mps"], vy * route["vehicle_speed_mps"], 0))
            frame = world.tick()
            time_s = float(world.get_snapshot().timestamp.elapsed_seconds)
            frame_map.append(frame, time_s)
            capture.capture(frame, time_s)
            pedestrian_xyz, pedestrian_forward = _transform(walker)
            vehicle_xyz, vehicle_forward = _transform(vehicle)
            observations.append({"frame": frame, "time_s": time_s,
                "pedestrian_xyz_m": pedestrian_xyz, "vehicle_xyz_m": vehicle_xyz,
                "pedestrian_forward_xy": pedestrian_forward,
                "vehicle_forward_xy": vehicle_forward,
                "observation_source": "original_native_snapshot"})
            for name in CAMERAS:
                encoders[name].stdin.write(bytes(_frame(queues[name], frame).raw_data))
        for process in encoders.values():
            process.stdin.close()
            if process.wait(timeout=120) != 0:
                raise RuntimeError("four-view walking encoder failed")
        frame_map.close()
        capture.close(confirmed=True)
        site = {"reviewed_public_highway": True, "reviewed_sidewalk_absent": True,
                "reviewed_subsection_6_inapplicable": True,
                "centerline_xy_m": packet["centerline_xy_m"],
                "reviewed_site_packet_sha256": sha(review_path)}
        source = {"assignment_id": case_id.rsplit("__", 1)[0], "case_id": case_id,
                  "diagnostic_fixture": False, "original_trace_id": "Native:" + sha(output / "trace.jsonl"),
                  "site_source_sha256": sha(review_path), "site": site, "frames": observations}
        write(output / "original-walking-observations.json", source)
        write(output / "original-walking-receipt.json", {"case_id": case_id, "fps": 20,
            "frame_count": len(observations), "diagnostic_fixture": False,
            "source_sha256": sha(output / "original-walking-observations.json"),
            "review_sha256": sha(review_path)})
    except BaseException as error:
        failure = error
    finally:
        if frame_map is not None and not frame_map.stream.closed:
            frame_map.close()
        if capture is not None and not capture.closed:
            capture.close(confirmed=False)
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for camera in cameras.values():
            try:
                camera.stop()
            finally:
                camera.destroy()
        for actor in reversed(actors):
            actor.destroy()
        try:
            restored = bool(restore(client, prior)["restored"])
        except BaseException as error:
            failure = failure or error
    write(output / "native-run-status.json", {"restored": restored,
        "capture_complete": failure is None, "errors": [repr(failure)] if failure else []})
    if failure or not restored:
        raise RuntimeError("original walking capture or restoration failed") from failure
    write(output / "acquisition-provenance.json", {"provenance_kind": "native",
        "diagnostic_fixture": False, "case_id": case_id, "review_sha256": sha(review_path)})
    seal_capture(output, frames=900, restoration={"restored": True}, errors=[],
        encoder_exit_codes={name: 0 for name in CAMERAS},
        context={"case_id": case_id, "review_sha256": sha(review_path)})
    return {"case_id": case_id, "frame_count": 900, "restored": True,
            "original_walking_source_sha256": sha(output / "original-walking-observations.json"),
            "physical_acceptance": False}
