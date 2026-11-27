"""Original Native one-way tunnel acquisition. A failed physical setup remains a failed attempt."""

import hashlib
import json
import math
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import traceback


CAMERAS = (("overview", 1920, 1080, (-18, -12, 25), 35, -50, False),
           ("approach", 1280, 720, (18, 6, 8), 180, -20, False),
           ("reference_corner", 1280, 720, (-3, -12, 8), 90, -20, False),
           ("driver_reference", 1280, 720, (1, 0, 2), 0, -8, True))
SOURCES = ("road.xodr", "portal-geometry.json", "road-direction-survey.json",
           "centreline-geometry.json", "vehicle-extents.jsonl", "sight-rays.jsonl",
           "tunnel-rows.jsonl", "trace.jsonl", "video_frames.jsonl",
           "capture/evidence.jsonl")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def repo():
    for parent in Path(__file__).resolve().parents:
        if (parent / "batch.json").is_file():
            return parent
    raise ValueError("Pinned repository unavailable")


def body(ego):
    transform = ego.get_transform()
    vertices = ego.bounding_box.get_world_vertices(transform)
    points = sorted({(round(v.x, 6), round(v.y, 6)) for v in vertices})
    if len(points) != 4:
        raise ValueError("Original four-corner body unavailable")
    return [list(p) for p in points]


def control(carla, ego, target_y, gain):
    transform = ego.get_transform()
    velocity = ego.get_velocity()
    speed = math.hypot(velocity.x, velocity.y)
    target_x = transform.location.x + 15
    angle = math.atan2(target_y - transform.location.y, target_x - transform.location.x)
    error = math.atan2(math.sin(angle - math.radians(transform.rotation.yaw)),
                       math.cos(angle - math.radians(transform.rotation.yaw)))
    return carla.VehicleControl(steer=max(-.7, min(.7, gain * error)),
        throttle=max(0, min(1, .22 + .22 * (3.4 - speed))),
        brake=max(0, min(1, .4 * (speed - 3.4))))


def run(bundle, output, host, port):
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Retain prior Native attempt; use a fresh output directory")
    output.mkdir(parents=True)
    shutil.copyfile(bundle / "config.json", output / "config.json")
    shutil.copyfile(bundle / "road.xodr", output / "road.xodr")
    root = repo()
    sys.path.insert(0, str(root / "runtime/scenario_pipeline"))
    sys.path.insert(1, str(root / "runtime/python"))
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from carla_sgg.law_evidence import actor_visibility
    from sight_proxy import incoming_lane_bracket
    from worker_exchange.media import compose_four_views
    from worker_exchange.native_output import seal_capture
    from worker_exchange.world_restore import snapshot, restore

    config = json.loads((output / "config.json").read_text())
    case = config["selected_case_id"]
    if case not in config["supported_case_ids"] or not case.endswith(("__one_way_right", "__one_way_left")):
        raise ValueError("Exact tunnel case unsupported")
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    original = client.get_world()
    if saved["settings"].synchronous_mode or any(
            actor.type_id.startswith(("vehicle.", "walker.", "sensor."))
            for actor in original.get_actors()):
        raise RuntimeError("Exclusive idle asynchronous CARLA world required")
    owned, encoders, logs, feeds = [], {}, {}, {}
    capture = None
    changed = False
    count = 0
    error = None
    restored = None
    try:
        world = client.generate_opendrive_world((output / "road.xodr").read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
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
        lanes = []
        for y, expected in ((-1.75, -1), (-5.25, -2)):
            waypoint = mapping.get_waypoint(carla.Location(x=-30, y=y, z=1),
                project_to_road=False, lane_type=carla.LaneType.Driving)
            lanes.append({"y_m": y, "road_id": None if waypoint is None else waypoint.road_id,
                          "lane_id": None if waypoint is None else waypoint.lane_id})
            if waypoint is None or waypoint.lane_id != expected:
                raise RuntimeError("Original one-way lane readback differs")
        put(output / "road-direction-survey.json", {"lanes": lanes,
            "one_way_native_survey": True, "native_map_sha256":
            hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            "physical_highway_verified": False})
        put(output / "centreline-geometry.json", {"centerline_y_m": -3.5,
            "source": "authored OpenDRIVE and original one-way lane readback",
            "native_direction_survey_sha256": digest(output / "road-direction-survey.json")})
        library = world.get_blueprint_library()
        tunnel_bp = library.find(config["tunnel_blueprint"])
        occluder_bp = library.find(config["occluder_blueprint"])
        tunnel = world.try_spawn_actor(tunnel_bp,
            carla.Transform(carla.Location(x=0, y=0, z=0)))
        if tunnel is None:
            raise RuntimeError("Original tunnel prop unavailable")
        owned.append(tunnel)
        occluder = world.try_spawn_actor(occluder_bp,
            carla.Transform(carla.Location(x=-10, y=5, z=0)))
        if occluder is None:
            raise RuntimeError("Original sight occluder unavailable")
        owned.append(occluder)
        put(output / "portal-geometry.json", {"structure_kind": "tunnel",
            "portal_x_m": 0, "tunnel_actor_id": tunnel.id,
            "tunnel_type_id": tunnel.type_id,
            "tunnel_bounds_native_xyz_m": [[v.x, v.y, v.z] for v in
                tunnel.bounding_box.get_world_vertices(tunnel.get_transform())],
            "occluder_actor_id": occluder.id,
            "physical_tunnel_identity_review": "pending_original_pixels_and_geometry"})
        vehicle_bp = library.find(config["vehicle_blueprint"])
        vehicle_bp.set_attribute("role_name", "c313130_ego")
        ego = world.try_spawn_actor(vehicle_bp,
            carla.Transform(carla.Location(x=-65, y=-5.25, z=1.5), carla.Rotation(yaw=0)))
        if ego is None:
            raise RuntimeError("Original tunnel ego unavailable")
        owned.append(ego)
        for _ in range(20):
            world.tick()
        for name, width, height, xyz, yaw, pitch, attached in CAMERAS:
            bp = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", 85), ("sensor_tick", 0)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(*xyz),
                carla.Rotation(yaw=yaw, pitch=pitch)), attach_to=ego if attached else None)
            owned.append(sensor)
            feeds[name] = queue.Queue()
            logs[name] = (output / (name + ".encoder.log")).open("x")
            encoders[name] = subprocess.Popen(["ffmpeg", "-nostdin", "-hide_banner",
                "-loglevel", "error", "-n", "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", f"{width}x{height}", "-r", "20", "-i", "pipe:0", "-an",
                "-c:v", "ffv1", "-level", "1", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=logs[name])
            sensor.listen(feeds[name].put)
        capture = PipelineCapture(client, ego, output, case,
            visibility=False, required_observations=[])
        start = world.get_snapshot().timestamp.elapsed_seconds + .05
        with (output / "vehicle-extents.jsonl").open("x") as extents, \
             (output / "sight-rays.jsonl").open("x") as rays, \
             (output / "tunnel-rows.jsonl").open("x") as rows, \
             (output / "video_frames.jsonl").open("x") as frame_map:
            for index in range(600):
                ego.apply_control(control(carla, ego,
                    -1.75 if case.endswith("__one_way_left") else -5.25,
                    config["controller_gain"]))
                native_frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                velocity = ego.get_velocity()
                footprint = body(ego)
                speed = math.hypot(velocity.x, velocity.y)
                lane = mapping.get_waypoint(ego.get_transform().location,
                    project_to_road=True, lane_type=carla.LaneType.Driving)
                original_visibility = actor_visibility(world, ego, mapping=mapping,
                    lane_inventory=capture.visibility_lane_inventory,
                    route_topology=capture.visibility_route_topology)
                ray = incoming_lane_bracket(original_visibility,
                    None if lane is None else lane.road_id,
                    None if lane is None else lane.lane_id)
                row = {"video_frame": index, "native_frame": native_frame,
                    "time_s": time_s, "source_cameras": {name: index for name, *_ in CAMERAS},
                    "body_xy_m": footprint, "observed_speed_mps": speed,
                    "incoming_lane_sight_ray": ray}
                capture.capture(native_frame, time_s, extra={"c313130_tunnel": row})
                extents.write(json.dumps({"native_frame": native_frame,
                    "body_xy_m": footprint}, allow_nan=False) + "\n")
                rays.write(json.dumps({"native_frame": native_frame,
                    "incoming_lane_sight_ray": ray}, allow_nan=False) + "\n")
                rows.write(json.dumps(row, allow_nan=False) + "\n")
                for name, width, height, *_ in CAMERAS:
                    image = feeds[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = feeds[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError("Original camera/Native frame join differs")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                frame_map.write(json.dumps({"video_frame": index,
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
            logs[name].close()
        for actor in reversed(owned):
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
        if error is None and count == 600:
            try:
                put(output / "acquisition-provenance.json", {"provenance_kind":
                    "original_native_attempt", "diagnostic_fixture": False})
                files = {name: digest(output / name) for name in SOURCES}
                direction = json.loads((output / "road-direction-survey.json").read_text())
                put(output / "tunnel-context.json", {"case_id": case,
                    "source_kind": "original_native_tunnel_map_and_ray_readback",
                    "structure_kind": "tunnel", "approach_portal_x_m": 0,
                    "highway_centre_y_m": -3.5, "one_way_native_survey": True,
                    "native_map_sha256": direction["native_map_sha256"],
                    "portal_geometry_sha256": files["portal-geometry.json"],
                    "road_direction_survey_sha256": files["road-direction-survey.json"],
                    "centreline_geometry_sha256": files["centreline-geometry.json"],
                    "vehicle_extent_sha256": files["vehicle-extents.jsonl"],
                    "sight_ray_source_sha256": files["sight-rays.jsonl"],
                    "source_files": {name: name for name in SOURCES},
                    "source_sha256": files, "physical_acceptance_claimed": False,
                    "tunnel_source_context": {"structure_kind": "tunnel",
                        "one_way_surveyed": True,
                        "original_native_observed": True}})
                sources = {name: output / (name + ".mkv") for name, *_ in CAMERAS}
                put(output / "four-view-receipt.json", compose_four_views(
                    sources, output / "video_frames.jsonl", output / "raw.mkv"))
                seal_capture(output, frames=count, restoration=restored, errors=[],
                    encoder_exit_codes={name: p.returncode for name, p in encoders.items()},
                    context={"case_id": case, "candidate_id": config["candidate_id"],
                             "physical_acceptance_claimed": False})
            except BaseException as exc:
                error = error or {"seal_error": str(exc)}
        put(output / "native-capture-report.json", {"case_id": case,
            "requested_frames": 600, "observed_frames": count,
            "restoration": restored, "error": error,
            "physical_acceptance_claimed": False, "legal_verdict": None})
    if error:
        raise RuntimeError("Native tunnel attempt failed; see native-capture-report.json")
