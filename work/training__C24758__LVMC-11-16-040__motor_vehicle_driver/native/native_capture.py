"""Draft original Native acquisition for exact C24758 reference primary.

Requires an exclusive idle CARLA world. It records raw sources only and leaves
visibility, exception, physical-completion and legal conclusions unset.
"""
import hashlib
import json
import math
import queue
import subprocess
from pathlib import Path

from saved_source import CAMERAS
from sight_speed_measure import EXPECTED_ID, require
from ray_inventory import sample_approaches, original_rays, xyz


def choose_route(mapping, junction_id):
    """Select a driving route with 45 m of approach and 15 m beyond a junction."""
    options = []
    for start, end in mapping.get_topology():
        for waypoint in (start, end):
            if not waypoint.is_junction:
                continue
            junction = waypoint.get_junction()
            if junction_id is not None and junction.id != junction_id:
                continue
            before = waypoint.previous(45.0)
            after = waypoint.next(15.0)
            if len(before) != 1 or len(after) != 1 or before[0].is_junction:
                continue
            options.append((junction.id, waypoint.road_id, waypoint.lane_id,
                            before[0], waypoint, after[0]))
    require(bool(options), "no unambiguous 45m junction approach in Native map")
    return sorted(options, key=lambda row: row[:3])[0]


def camera_specs(carla, ego, target):
    loc = target.transform.location
    def world_camera(dx, dy, dz):
        pose = carla.Location(x=loc.x + dx, y=loc.y + dy, z=loc.z + dz)
        yaw = math.degrees(math.atan2(loc.y - pose.y, loc.x - pose.x))
        pitch = math.degrees(math.atan2(loc.z - pose.z, math.hypot(loc.x-pose.x,loc.y-pose.y)))
        return carla.Transform(pose, carla.Rotation(yaw=yaw, pitch=pitch)), None
    return {
        "overview": world_camera(-18, -18, 16),
        "approach": world_camera(-35, -8, 8),
        "reference_corner": world_camera(8, 8, 6),
        "driver_reference": (carla.Transform(carla.Location(x=0.5, z=1.6)), ego)
    }


def capture(config, output, host, port, junction_id=None):
    import carla
    import numpy as np
    from worker_exchange.world_restore import snapshot, restore

    output = Path(output).resolve()
    require(output.is_dir() and (output / "config.json").is_file(),
            "capture requires a fresh materialized exact-case directory")
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    original = snapshot(client)
    world = client.get_world()
    require(not world.get_settings().synchronous_mode, "requires exclusive asynchronous world")
    require(not any(a.type_id.startswith(("vehicle.", "walker.", "sensor."))
                    for a in world.get_actors()), "requires idle world")
    owned = []
    encoders = {}
    queues = {}
    logs = {}
    frames = []
    raw = []
    error = None
    try:
        mapping = world.get_map()
        chosen_id, road_id, lane_id, before, junction, after = choose_route(mapping, junction_id)
        entering = []
        for entry, exit_waypoint in junction.get_junction().get_waypoints(carla.LaneType.Driving):
            entering.append({"road_id": entry.road_id, "lane_id": entry.lane_id,
                             "entry_xyz_m": [entry.transform.location.x,
                                             entry.transform.location.y,
                                             entry.transform.location.z],
                             "exit_road_id": exit_waypoint.road_id,
                             "exit_lane_id": exit_waypoint.lane_id})
        require(len(entering) >= 2, "entering Native driving approaches missing")
        approach_samples = sample_approaches(junction.get_junction(), carla.LaneType.Driving)
        signal_actors = []
        for actor in world.get_actors():
            if actor.type_id.startswith("traffic.traffic_light"):
                loc = actor.get_location()
                if loc.distance(junction.transform.location) <= 100:
                    signal_actors.append({"actor_id": actor.id, "type_id": actor.type_id,
                                          "xyz_m": [loc.x, loc.y, loc.z]})
        xodr = mapping.to_opendrive()
        (output / "native-map-readback.xodr").write_text(xodr)
        setup = {"assignment_id": EXPECTED_ID, "case_id": config["case_id"],
                 "native_map_name": mapping.name, "native_map_sha256": hashlib.sha256(xodr.encode()).hexdigest(),
                 "junction_id": chosen_id, "road_id": road_id, "lane_id": lane_id,
                 "approach_waypoint_xyz_m": [before.transform.location.x, before.transform.location.y, before.transform.location.z],
                 "boundary_waypoint_xyz_m": [junction.transform.location.x, junction.transform.location.y, junction.transform.location.z],
                 "departure_waypoint_xyz_m": [after.transform.location.x, after.transform.location.y, after.transform.location.z],
                 "native_entering_driving_lanes": entering,
                 "entering_approach_ray_targets": approach_samples,
                 "nearby_native_signal_actors": signal_actors,
                 "intersection_sight_reviewed": False, "all_entering_traffic_visibility_reviewed": False,
                 "through_street_exception_reviewed": False, "traffic_control_exception_reviewed": False,
                 "physical_completion": None, "legal_verdict": None}
        (output / "native-context-readback.json").write_text(json.dumps(setup, indent=2) + "\n")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        spawn = before.transform
        spawn.location.z += 0.5
        vehicle_bp = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        vehicle_bp.set_attribute("role_name", "c24758_lvmc_11_16_040_" + config["case_id"].rsplit("__", 1)[-1] + "_ego")
        ego = world.spawn_actor(vehicle_bp, spawn)
        owned.append(ego)
        specs = camera_specs(carla, ego, junction)
        for name in CAMERAS:
            plan = next(c for c in config["cameras"] if c["name"] == name)
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", plan["width"]),
                               ("image_size_y", plan["height"]),
                               ("fov", plan["fov_deg"]), ("sensor_tick", 0)):
                bp.set_attribute(key, str(value))
            transform, attach = specs[name]
            camera = world.spawn_actor(bp, transform, attach_to=attach)
            owned.append(camera)
            q = queue.Queue()
            queues[name] = q
            camera.listen(q.put)
            log = (output / f"{name}.encoder.log").open("x")
            logs[name] = log
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", f"{plan['width']}x{plan['height']}", "-r", "20", "-i", "pipe:0",
                "-an", "-c:v", "ffv1", str(output / f"{name}.mkv")],
                stdin=subprocess.PIPE, stderr=log)
        initial = world.get_snapshot().timestamp.elapsed_seconds
        target_speed = config["target_speed_mps"]
        for i in range(600):
            speed = ego.get_velocity().length()
            error_speed = target_speed - speed
            ego.apply_control(carla.VehicleControl(throttle=max(0.0, min(0.55, 0.12 * error_speed)),
                                                    brake=max(0.0, min(0.8, -0.18 * error_speed)),
                                                    steer=0))
            frame = world.tick()
            stamp = world.get_snapshot().timestamp.elapsed_seconds - initial
            pose = ego.get_transform()
            velocity = ego.get_velocity()
            current_lane = mapping.get_waypoint(pose.location, project_to_road=True,
                                                lane_type=carla.LaneType.Driving)
            current_junction = current_lane.get_junction() if current_lane and current_lane.is_junction else None
            eye = pose.transform(carla.Location(x=0.5, z=1.6))
            sight_targets = [{"target": "intersection", "xyz_m": xyz(junction.transform.location)}]
            for approach_id, points in approach_samples.items():
                for point in points:
                    sight_targets.append({"target": approach_id,
                                          "distance_from_intersection_ft": point["distance_from_intersection_ft"],
                                          "xyz_m": point["xyz_m"]})
            ray_hits = original_rays(world, carla, eye, [target["xyz_m"] for target in sight_targets])
            camera_hashes = {}
            for name in CAMERAS:
                image = queues[name].get(timeout=30)
                while image.frame < frame:
                    image = queues[name].get(timeout=30)
                require(image.frame == frame, f"camera/frame join failed: {name}")
                pixels = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                    image.height, image.width, 4)[:, :, :3][:, :, ::-1].tobytes()
                camera_hashes[name] = hashlib.sha256(pixels).hexdigest()
                encoders[name].stdin.write(pixels)
            frames.append({"video_frame": i, "native_frame": frame, "time_s": i / 20,
                           "native_elapsed_s": stamp, "original_rgb_sha256": camera_hashes})
            raw.append({"video_frame": i, "native_frame": frame, "native_elapsed_s": stamp,
                        "ego_xyz_m": [pose.location.x, pose.location.y, pose.location.z],
                        "ego_yaw_deg": pose.rotation.yaw,
                        "ego_velocity_xyz_mps": [velocity.x, velocity.y, velocity.z],
                        "ego_speed_mps": velocity.length(),
                        "distance_to_boundary_euclidean_m": pose.location.distance(junction.transform.location),
                        "ego_native_junction_id": current_junction.id if current_junction else None,
                        "ego_traffic_light_state": str(ego.get_traffic_light_state()) if ego.is_at_traffic_light() else None,
                        "driver_eye_xyz_m": xyz(eye),
                        "sight_targets": sight_targets,
                        "original_native_sight_rays": ray_hits,
                        "driver_eye_sight_reviewed": False,
                        "entering_approach_visibility_reviewed": False})
        require(len(frames) == 600, "incomplete Native frame count")
        (output / "frame-map.json").write_text(json.dumps(frames) + "\n")
        with (output / "native-ego-readback.jsonl").open("x") as f:
            for row in raw:
                f.write(json.dumps(row) + "\n")
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                require(encoder.wait(timeout=180) == 0, f"encoder failed: {name}")
            except BaseException as exc:
                error = error or {"encoder_error": str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor."):
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"cleanup_error": str(exc)}
        try:
            restore(client, original)
        except BaseException as exc:
            error = error or {"restore_error": str(exc)}
        (output / "native-attempt-status.json").write_text(json.dumps({
            "frames": len(frames), "error": error, "physical_completion": None,
            "legal_verdict": None}, indent=2) + "\n")
    require(error is None, f"Native capture failed: {error}")
    return {"frames": len(frames), "physical_completion": None,
            "legal_verdict": None}
