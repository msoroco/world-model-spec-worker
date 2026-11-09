"""Unaccepted original CARLA attempt for the C104496 grade-crest pair."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from build import FRAMES, RATE, elevation
from check import check
from saved import observer_station


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def xyz(v):
    return [v.x, v.y, v.z]


def body(actor):
    pose = actor.get_transform()
    velocity = actor.get_velocity()
    return {"actor_id": actor.id, "blueprint": actor.type_id,
            "center_native_xyz_m": xyz(pose.location), "yaw_deg": pose.rotation.yaw,
            "velocity_native_xyz_mps": xyz(velocity),
            "speed_mps": math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
            "body_native_xyz_m": [xyz(p) for p in actor.bounding_box.get_world_vertices(pose)]}


def body_rays(world, ego, eye, carla):
    pose = ego.get_transform()
    corners = list(ego.bounding_box.get_world_vertices(pose))
    center = carla.Location(x=sum(p.x for p in corners)/8,
                            y=sum(p.y for p in corners)/8,
                            z=sum(p.z for p in corners)/8)
    rays = []
    for endpoint in corners + [center]:
        blockers = []
        for hit in world.cast_ray(eye, endpoint):
            if ego.bounding_box.contains(hit.location, pose):
                continue
            if hit.location.distance(eye) < .05 or hit.location.distance(endpoint) < .02:
                continue
            blockers.append({"label": str(hit.label), "location_m": xyz(hit.location)})
        rays.append({"eye_m": xyz(eye), "body_sample_m": xyz(endpoint),
                     "blockers": blockers, "clear": not blockers})
    return rays


def control_for(actor, request, carla):
    phase = request["requested_motion_phase"]
    if phase == "stop_before_crest":
        return carla.VehicleControl(throttle=0, brake=1, steer=0)
    reverse = phase == "reverse_right"
    desired_yaw = math.degrees(request["requested_heading_rad"])
    actual_yaw = actor.get_transform().rotation.yaw
    error = (desired_yaw - actual_yaw + 180) % 360 - 180
    speed = actor.get_velocity()
    actual_speed = math.sqrt(speed.x**2 + speed.y**2 + speed.z**2)
    steering = max(-.8, min(.8, (-1 if reverse else 1) * error / 40))
    throttle = max(.1, min(.65, .25 + .12 * (request["requested_speed_mps"] - actual_speed)))
    return carla.VehicleControl(throttle=throttle, steer=steering, reverse=reverse,
                                manual_gear_shift=False)


def capture(bundle, output, host, port):
    import carla
    import numpy as np
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    checked = check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requests = [json.loads(line) for line in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    client = carla.Client(host, int(port)); client.set_timeout(180)
    prior = client.get_world()
    saved_world = snapshot(client)
    if prior.get_settings().synchronous_mode or any(a.type_id.startswith(("vehicle.", "walker.", "sensor."))
                                                 for a in prior.get_actors()):
        raise RuntimeError("Exclusive idle asynchronous CARLA world required")
    output.mkdir(parents=True, exist_ok=False)
    owned, sensors, encoders, logs = [], {}, {}, {}
    changed = False; frames = 0; error = None; restoration = None; map_readback = None
    try:
        world = client.generate_opendrive_world((bundle / "crest.xodr").read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings(); settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map(); map_readback = {}
        for name, lane_id, station in (("west_500ft", 1, 47.6), ("ego_approach", -1, 180),
                                       ("crest", -1, 200), ("east_500ft", -1, 352.4)):
            wp = mapping.get_waypoint_xodr(407, lane_id, station)
            map_readback[name] = None if wp is None else {
                "road_id": wp.road_id, "lane_id": wp.lane_id,
                "lane_type": str(wp.lane_type), "native_xyz_m": xyz(wp.transform.location)}
            if wp is None or wp.road_id != 407 or wp.lane_id != lane_id or wp.lane_type != carla.LaneType.Driving:
                raise RuntimeError("Generated crest lane readback differs: " + name)
            if abs(wp.transform.location.z - elevation(station, cfg["grade_height_m"])) > 1.0:
                raise RuntimeError("Generated grade elevation differs: " + name)
        library = world.get_blueprint_library()
        ego_bp = library.find(cfg["ego_blueprint"])
        other_bp = library.find(cfg["other_vehicle_blueprint"])
        ego = world.try_spawn_actor(ego_bp, carla.Transform(carla.Location(
            x=180, y=-1.75, z=elevation(180, cfg["grade_height_m"])+1.5)))
        other = world.try_spawn_actor(other_bp, carla.Transform(carla.Location(
            x=47.6, y=1.75, z=elevation(47.6, cfg["grade_height_m"])+1.5)))
        if ego is None or other is None:
            raise RuntimeError("Ego or approaching-vehicle spawn failed")
        owned.extend((ego, other))
        elevated = cfg["camera_policy"] == "elevated_overview"
        specs = (("west_view", 1280, 720, (47.6, 1.75, elevation(47.6, cfg["grade_height_m"])+1.4), 0, 0),
                 ("east_view", 1280, 720, (352.4, -1.75, elevation(352.4, cfg["grade_height_m"])+1.4), 180, 0),
                 ("overview", 1280, 720, (200, -25, elevation(200, cfg["grade_height_m"])+(50 if elevated else 35)), 90, -65))
        for name, width, height, location, yaw, pitch in specs:
            bp = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", 80), ("sensor_tick", 0)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(bp, carla.Transform(carla.Location(*location),
                                                         carla.Rotation(yaw=yaw, pitch=pitch)))
            owned.append(sensor); sensors[name] = queue.Queue(); sensor.listen(sensors[name].put)
            logs[name] = (output / (name + ".encoder.log")).open("x")
            encoders[name] = subprocess.Popen(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-n", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
                "-r", str(RATE), "-i", "pipe:0", "-an", "-c:v", "ffv1",
                str(output / (name + ".mkv"))], stdin=subprocess.PIPE, stderr=logs[name])
        (output / "native-map-readback.json").write_text(json.dumps({
            "source_kind": "original_native", "road_sha256": sha(bundle / "crest.xodr"),
            "native_map_sha256": hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            "lane_readback": map_readback, "ego_actor_id": ego.id, "other_actor_id": other.id,
            "legal_verdict": None}, indent=2) + "\n")
        for _ in range(20): world.tick()
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / "native-raw-actors.jsonl").open("x") as actor_file, \
             (output / "video_frames.jsonl").open("x") as video_file:
            for i, request in enumerate(requests):
                next_request = requests[min(i+5, FRAMES-1)]
                ego.apply_control(control_for(ego, next_request, carla))
                other.set_target_velocity(carla.Vector3D(x=4, y=0, z=0))
                native_frame = world.tick()
                t = world.get_snapshot().timestamp.elapsed_seconds - start
                ego_state = body(ego); other_state = body(other)
                subject_x = ego_state["center_native_xyz_m"][0]
                stations = [observer_station(subject_x, cfg["grade_height_m"], direction)
                            for direction in (-1, 1)] if 0 <= subject_x <= 450 else [None, None]
                rays = []
                for station, lane_id in zip(stations, (1, -1)):
                    if station is None:
                        rays.append(None)
                    else:
                        observer_wp = mapping.get_waypoint_xodr(407, lane_id, station)
                        if observer_wp is None or observer_wp.lane_type != carla.LaneType.Driving:
                            raise RuntimeError("Generated 500-foot observer lane absent")
                        eye = observer_wp.transform.location + carla.Location(z=1.4)
                        rays.append(body_rays(world, ego, eye, carla))
                wp = mapping.get_waypoint(ego.get_location(), project_to_road=False,
                                          lane_type=carla.LaneType.Any)
                row = {"frame": i, "native_frame": native_frame, "time_s": t,
                       "source_kind": "original_native", "request_frame": request["frame"],
                       "ego": ego_state, "other": other_state,
                       "ego_road_id": None if wp is None else wp.road_id,
                       "ego_lane_id": None if wp is None else wp.lane_id,
                       "observer_stations_m": stations, "body_rays_by_approach": rays,
                       "requested_motion_phase": request["requested_motion_phase"],
                       "human_visibility_reviewed": False, "legal_verdict": None}
                actor_file.write(json.dumps(row, allow_nan=False) + "\n")
                for name, width, height, _, _, _ in specs:
                    image = sensors[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = sensors[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError("Camera/native frame join failed")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                video_file.write(json.dumps({"video_frame": i, "native_frame": native_frame,
                                             "time_s": t}) + "\n")
                frames += 1
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    finally:
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError("FFV1 encoder failed")
            except BaseException as exc:
                error = error or {"encoder_error": str(exc)}
            logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening: actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"cleanup_error": str(exc)}
        if changed:
            try: restoration = restore(client, saved_world)
            except BaseException as exc: error = error or {"restore_error": str(exc)}
        (output / "native-capture-report.json").write_text(json.dumps({
            "case_id": checked["case_id"], "candidate_id": checked["candidate"],
            "config_sha256": sha(bundle / "config.json"), "requested_frames": FRAMES,
            "observed_frames": frames, "restoration": restoration, "error": error,
            "accepted": False, "delivery_ready": False, "legal_verdict": None}, indent=2) + "\n")
    if error:
        raise RuntimeError("C104496 original Native attempt failed; inspect capture report")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--bundle", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(args.bundle)))
    else:
        if args.output_dir is None:
            parser.error("Original Native output directory required")
        capture(args.bundle, args.output_dir, args.host, args.port)
