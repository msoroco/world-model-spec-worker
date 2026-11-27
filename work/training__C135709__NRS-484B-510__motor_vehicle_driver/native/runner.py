"""Prospective original Native restricted-zone capture.

The output is a source packet for independent review, never an accepted legal
or physical result. CARLA is imported only when execute() is invoked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import xml.etree.ElementTree as ET

from capture_plan import AID, CAMERAS, CASES, build
from geometry import SIGN_ID, check as geometry_check, open_drive
from parking_controller import ParkingPlan, command

RATE = 20
FRAMES = 600
MOUNTS = {"overview": (-5, -18, 18, -36),
          "approach": (-22, -12, 8, -16),
          "reference_corner": (10, -11, 7, -19),
          "driver_reference": (35, -11, 8, -20)}


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def check(request: dict) -> dict:
    case_id = request.get("case_id")
    require(isinstance(case_id, str) and case_id.startswith(AID + "__"),
            "exact restricted-zone case required")
    suffix = case_id[len(AID) + 2:]
    speed_cap = request.get("primary_max_speed_mps")
    require(suffix in CASES and speed_cap in (3.0, 4.0) and
            request == build(suffix, approach_speed_cap_mps=speed_cap),
            "Native request differs from exact construction plan")
    geometry = geometry_check()
    require(request["frames"] == FRAMES and request["fps"] == RATE and
            request["duration_s"] == 30 and request["camera_sizes"] == CAMERAS,
            "exact 30-second four-camera profile changed")
    return {"case_id": case_id, "frames": FRAMES, "geometry": geometry,
            "original_native_observed": False, "legal_conclusion": None}


def body(actor) -> list[float]:
    transform = actor.get_transform()
    extent = actor.bounding_box.extent
    x, y = transform.location.x, transform.location.y
    yaw = math.radians(transform.rotation.yaw)
    co, si = math.cos(yaw), math.sin(yaw)
    corners = [(x + dx * co - dy * si, y + dx * si + dy * co)
               for dx, dy in ((-extent.x, -extent.y), (extent.x, -extent.y),
                              (extent.x, extent.y), (-extent.x, extent.y))]
    return [min(p[0] for p in corners), min(p[1] for p in corners),
            max(p[0] for p in corners), max(p[1] for p in corners)]


def speed(actor) -> float:
    value = actor.get_velocity()
    return math.sqrt(value.x * value.x + value.y * value.y + value.z * value.z)


def execute(request: dict, output_dir: Path, host: str, port: int) -> dict:
    check(request)
    output = Path(output_dir).resolve()
    source = Path(__file__).resolve()
    scratch_root = next((parent for parent in source.parents
                         if parent.name == ".runtime-work"), None)
    if scratch_root is None:
        scratch_root = (source.parents[3] / ".runtime-work").resolve()
    require(output.is_relative_to(scratch_root),
            "original attempt must remain under .runtime-work")
    bundle_names = {"runner.py", "capture_plan.py", "geometry.py",
                    "parking_controller.py", "config.json", "construction.json",
                    "candidate-selection.json", "tests", "offline.log"}
    require(output.is_dir() and
            all(path.name in bundle_names for path in output.iterdir()),
            "fresh materialized original attempt directory required")
    require(not any((output / name).exists() for name in (
        "road.xodr", "zone-survey.json", "actor-frames.jsonl",
        "camera-frames.jsonl", "capture-manifest.json",
        *(f"{name}.mkv" for name in CAMERAS))),
        "original source output already exists")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    prior = client.get_world()
    require(not saved["settings"].synchronous_mode and not any(
        actor.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))
        for actor in prior.get_actors()), "exclusive idle asynchronous Native world required")
    owned, encoders, camera_queues = [], {}, {}
    encoder_exit_codes = {}
    pipeline_capture = None
    world_changed = finished = False
    try:
        world = client.generate_opendrive_world(open_drive(),
            carla.OpendriveGenerationParameters(vertex_distance=.5,
                max_road_length=25, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=True))
        world_changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        map_text = world.get_map().to_opendrive()
        root = ET.fromstring(map_text)
        signs = [s for s in root.findall(".//signal") if s.attrib.get("id") == SIGN_ID]
        require(len(signs) == 1, "original restricted-purpose sign missing from Native map")
        (output / "road.xodr").write_text(map_text, encoding="utf-8")
        map_sha = hashlib.sha256((output / "road.xodr").read_bytes()).hexdigest()
        (output / "zone-survey.json").write_text(json.dumps({
            "bounds_m": request["requested_zone_bounds_m"], "map_sha256": map_sha,
            "sign_id": SIGN_ID, "sign_text_readback": signs[0].attrib.get("name"),
            "sign_authority": "unverified", "sign_pixels": "unverified",
            "effective_conditions": "unverified"}, sort_keys=True) + "\n", encoding="utf-8")
        library = world.get_blueprint_library()
        ego_bp = library.find("vehicle.tesla.model3")
        ego_bp.set_attribute("role_name", "c135709_restricted_zone_subject")
        ego = world.spawn_actor(ego_bp, carla.Transform(
            carla.Location(x=-25, y=-2.5, z=1), carla.Rotation(yaw=0)))
        owned.append(ego)
        other = None
        if request["waiting_vehicle_request"]:
            other_bp = library.find("vehicle.audi.a2")
            other_bp.set_attribute("role_name", "c135709_waiting_request")
            other = world.spawn_actor(other_bp, carla.Transform(
                carla.Location(x=10.5, y=-2.5, z=1), carla.Rotation(yaw=0)))
            owned.append(other)
        for name, (width, height) in CAMERAS.items():
            x, y, z, pitch = MOUNTS[name]
            bp = library.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(width))
            bp.set_attribute("image_size_y", str(height))
            bp.set_attribute("fov", "85")
            bp.set_attribute("sensor_tick", str(1 / RATE))
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z), carla.Rotation(pitch=pitch)))
            owned.append(camera)
            q = queue.Queue()
            camera.listen(q.put)
            camera_queues[name] = q
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}",
                "-r", str(RATE), "-i", "-", "-frames:v", str(FRAMES),
                "-c:v", "ffv1", "-level", "1", str(output / f"{name}.mkv")],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        motion = ParkingPlan(target_center_x_m=request["parking_target_center_x_m"],
                             max_speed_mps=request["primary_max_speed_mps"])
        pedestrians = []
        pipeline_capture = PipelineCapture(client, ego, output, request["case_id"],
                                           required_observations=[])
        with (output / "actor-frames.jsonl").open("x", encoding="utf-8") as actor_rows, \
                (output / "camera-frames.jsonl").open("x", encoding="utf-8") as camera_rows, \
                (output / "trace.jsonl").open("x", encoding="utf-8") as trace_rows, \
                FrameMap(output / "video_frames.jsonl") as frame_map:
            for index in range(FRAMES):
                if request["passenger_exchange_request"] and index == 100:
                    bp = sorted(library.filter("walker.pedestrian.*"), key=lambda x: x.id)[0]
                    person = world.try_spawn_actor(bp, carla.Transform(
                        carla.Location(x=5, y=-4.4, z=1)))
                    if person is not None:
                        owned.append(person)
                        pedestrians.append(person)
                departure_requested = (request["departure_frame"] is not None and
                                       index >= request["departure_frame"])
                control = ({"throttle": 0.35, "brake": 0.0} if departure_requested else
                           command(motion, ego.get_transform().location.x, speed(ego)))
                ego.apply_control(carla.VehicleControl(
                    throttle=control["throttle"], brake=control["brake"]))
                if other is not None:
                    other.apply_control(carla.VehicleControl(throttle=0, brake=1,
                                                              hand_brake=True))
                door_request = bool(request["passenger_exchange_request"] and
                                    95 <= index <= 105)
                if door_request:
                    require(hasattr(ego, "open_door"),
                            "Native passenger-door control unavailable")
                    ego.open_door(carla.VehicleDoor.FR)
                native_frame = world.tick()
                require(world.get_snapshot().frame == native_frame,
                        "Native frame/snapshot identity mismatch")
                pipeline_capture.capture(native_frame, index / RATE)
                cameras = {}
                for name, q in camera_queues.items():
                    image = q.get(timeout=30)
                    while image.frame < native_frame:
                        image = q.get(timeout=30)
                    require(image.frame == native_frame,
                            "original camera frame mismatch: " + name)
                    encoders[name].stdin.write(image.raw_data)
                    cameras[name] = index
                frame_map.append(native_frame, index / RATE,
                                 camera_native_frames={name: native_frame for name in CAMERAS})
                ego_body = body(ego)
                ego_pose = ego.get_transform()
                ego_velocity = ego.get_velocity()
                ego_speed = speed(ego)
                trace_rows.write(json.dumps({"frame": native_frame, "time_s": index / RATE,
                    "position_m": [(ego_body[0] + ego_body[2]) / 2,
                                   (ego_body[1] + ego_body[3]) / 2],
                    "position": {"x": ego_pose.location.x, "y": ego_pose.location.y,
                                 "z": ego_pose.location.z},
                    "heading_deg": ego_pose.rotation.yaw,
                    "velocity_mps": [ego_velocity.x, ego_velocity.y, ego_velocity.z],
                    "speed_mps": ego_speed}, sort_keys=True) + "\n")
                nearby = [person.id for person in pedestrians if
                          person.get_location().distance(ego.get_location()) <= 5]
                others = [] if other is None else [{"actor_id": other.id,
                    "body_m": body(other), "speed_mps": speed(other),
                    "requesting_zone_entry": True}]
                actor_rows.write(json.dumps({"frame": index,
                    "native_frame": native_frame, "elapsed_s": index / RATE,
                    "ego_body_m": ego_body, "ego_speed_mps": ego_speed,
                    "departure_requested": departure_requested,
                    "passenger_actor_ids_near_vehicle": nearby,
                    "door_open_request": door_request, "other_vehicles": others},
                    sort_keys=True) + "\n")
                camera_rows.write(json.dumps({"frame": index,
                    "native_frame": native_frame, "cameras": cameras},
                    sort_keys=True) + "\n")
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            encoder_exit_codes[name] = process.wait(timeout=180)
            require(encoder_exit_codes[name] == 0,
                    "original camera encoding failed: " + name + " " + stderr.decode()[-300:])
        pipeline_capture.close(confirmed=True)
        pipeline_capture = None
        finished = True
    finally:
        if pipeline_capture is not None:
            pipeline_capture.close(confirmed=False)
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
        restoration = restore(client, saved) if world_changed else {"restored": True}
        if finished:
            require(restoration.get("restored") is True,
                    "Native world restoration unverified")
            (output / "capture-manifest.json").write_text(json.dumps({
                "source_kind": "original_native", "case_id": request["case_id"],
                "frame_count": FRAMES, "fps": RATE, "closed": True,
                "world_restored": True, "map_sha256": map_sha,
                "video_sources": {name: {"path": f"{name}.mkv",
                    "sha256": hashlib.sha256((output / f"{name}.mkv").read_bytes()).hexdigest()}
                    for name in CAMERAS},
                "sign_authority": "unverified", "actual_passenger_loading": "unverified",
                "legal_conclusion": None}, sort_keys=True) + "\n", encoding="utf-8")
            seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                         encoder_exit_codes=encoder_exit_codes,
                         context={"case_id": request["case_id"],
                                  "original_sign_authority": "unverified"})
    return {"case_id": request["case_id"], "frames": FRAMES,
            "independent_source_review_required": True,
            "physical_acceptance_claimed": False, "legal_conclusion": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=sorted(CASES))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    suffix = args.case
    if suffix is None and Path("config.json").is_file():
        case_id = json.loads(Path("config.json").read_text()).get("case_id", "")
        if case_id.startswith(AID + "__"):
            suffix = case_id[len(AID) + 2:]
    require(suffix in CASES, "exact case required by --case or config.json")
    speed_cap = 4.0
    if Path("config.json").is_file():
        config = json.loads(Path("config.json").read_text())
        require(config.get("case_id") == AID + "__" + suffix,
                "materialized exact case differs")
        speed_cap = config.get("approach_speed_cap_mps", 4.0)
    request = build(suffix, approach_speed_cap_mps=speed_cap)
    if args.check:
        print(json.dumps(check(request), sort_keys=True))
    else:
        require(args.output_dir is not None, "--output-dir required for Native capture")
        print(json.dumps(execute(request, args.output_dir, args.host, args.port), sort_keys=True))
