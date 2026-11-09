"""Unaccepted original CARLA attempt for the C111603 red-plus-arrow request.

The two authored signal heads must both become distinct Native actors. A green
Native light state alone does not prove an illuminated directional arrow.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from build import FRAMES, RATE, check, digest

CAMERAS = ("ego_view", "signal_view", "overview")


def xyz(value):
    return [value.x, value.y, value.z]


def actor_row(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    return {"actor_id": actor.id, "blueprint": actor.type_id,
            "center_native_xyz_m": xyz(transform.location),
            "yaw_deg": transform.rotation.yaw,
            "velocity_native_xyz_mps": xyz(velocity),
            "speed_mps": math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
            "body_native_xyz_m": [xyz(v) for v in
                                  actor.bounding_box.get_world_vertices(transform)]}


def vehicle_control(actor, target, carla):
    location = actor.get_location()
    heading = math.radians(actor.get_transform().rotation.yaw)
    velocity = actor.get_velocity()
    speed = math.hypot(velocity.x, velocity.y)
    x, y, _ = target["requested_ego_xyz_m"]
    heading_error = (target["requested_heading_rad"] - heading + math.pi) % (2 * math.pi) - math.pi
    lateral = -(x - location.x) * math.sin(heading) + (y - location.y) * math.cos(heading)
    steer = max(-1.0, min(1.0, 0.9 * heading_error + 0.08 * lateral))
    if target["requested_phase"] == "yield_hold":
        return carla.VehicleControl(throttle=0, brake=min(1.0, 0.45 + speed / 5), steer=steer)
    goal = math.hypot(x - location.x, y - location.y)
    if goal < 0.5:
        return carla.VehicleControl(throttle=0, brake=min(1.0, 0.3 + speed / 5), steer=steer)
    return carla.VehicleControl(throttle=max(0.08, min(0.65, 0.25 + 0.1 * (goal - speed))),
                                brake=0, steer=steer)


def other_control(actor, target_x, carla):
    speed = actor.get_velocity().x
    error = target_x - actor.get_location().x
    if error < 0.3:
        return carla.VehicleControl(throttle=0, brake=min(1.0, 0.35 + max(0, speed) / 5))
    return carla.VehicleControl(throttle=max(0.08, min(0.55, 0.22 + 0.08 * (error - speed))),
                                brake=0)


def capture(bundle, output, host, port):
    import carla
    import numpy as np
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requests = [json.loads(line) for line in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    previous = client.get_world()
    saved_world = snapshot(client)
    if previous.get_settings().synchronous_mode or any(
            actor.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))
            for actor in previous.get_actors()):
        raise RuntimeError("Exclusive idle asynchronous CARLA world required")
    output.mkdir(parents=True, exist_ok=False)
    owned, sensors, encoders, logs = [], {}, {}, {}
    changed = False
    frames = 0
    error = restoration = None
    try:
        world = client.generate_opendrive_world(
            (bundle / "arrow-intersection.xodr").read_text(),
            carla.OpendriveGenerationParameters(vertex_distance=.25, max_road_length=100,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        lanes = {}
        for name, road_id, lane_id, station in (
                ("south_approach", 1, -1, 60),
                ("east_departure", 2, -1, 25)):
            waypoint = mapping.get_waypoint_xodr(road_id, lane_id, station)
            if waypoint is None or waypoint.road_id != road_id or waypoint.lane_type != carla.LaneType.Driving:
                raise RuntimeError("Generated lane readback missing: " + name)
            lanes[name] = {"road_id": waypoint.road_id, "lane_id": waypoint.lane_id,
                           "native_xyz_m": xyz(waypoint.transform.location)}
        signal_actors = list(world.get_actors().filter("traffic.traffic_light*"))
        if len(signal_actors) < 2:
            raise RuntimeError("Two distinct generated Native signal actors required")
        approach = sorted(signal_actors, key=lambda actor: math.hypot(
            actor.get_location().x - 4, actor.get_location().y + 13))[:2]
        if any(math.hypot(actor.get_location().x - 4, actor.get_location().y + 13) > 10
               for actor in approach):
            raise RuntimeError("Approach signal actors lack spatial readback")
        red, arrow = sorted(approach, key=lambda actor: actor.get_location().x)
        if red.id == arrow.id:
            raise RuntimeError("Red and arrow heads collapsed into one actor")
        red.set_state(carla.TrafficLightState.Red)
        red.freeze(True)
        arrow.set_state(carla.TrafficLightState.Green)
        arrow.freeze(True)
        library = world.get_blueprint_library()
        ego = world.try_spawn_actor(library.find(cfg["ego_blueprint"]), carla.Transform(
            carla.Location(x=-1.75, y=-50, z=1.5), carla.Rotation(yaw=90)))
        if ego is not None:
            owned.append(ego)
        other = world.try_spawn_actor(library.find(cfg["other_blueprint"]), carla.Transform(
            carla.Location(x=-30, y=2, z=1.5), carla.Rotation(yaw=0)))
        if other is not None:
            owned.append(other)
        if ego is None or other is None:
            raise RuntimeError("Both physical vehicles must spawn")
        (output / "native-map-readback.json").write_text(json.dumps({
            "source_kind": "original_native", "road_sha256": digest(bundle / "arrow-intersection.xodr"),
            "native_map_sha256": hashlib.sha256(mapping.to_opendrive().encode()).hexdigest(),
            "lane_readback": lanes, "red_actor_id": red.id, "arrow_actor_id": arrow.id,
            "red_actor_xyz_m": xyz(red.get_location()),
            "arrow_actor_xyz_m": xyz(arrow.get_location()),
            "ego_actor_id": ego.id, "other_actor_id": other.id,
            "directional_arrow_pixels_verified": False,
            "signal_governs_ego_verified": False,
            "other_traffic_lawfulness_verified": False,
            "legal_verdict": None}, indent=2) + "\n")
        overview_z = 55 if cfg["camera_policy"] == "elevated_overview" else 38
        specs = (("ego_view", 1280, 720, (-2, -35, 4), 0, -5),
                 ("signal_view", 1280, 720, (5, -16, 8), -90, -30),
                 ("overview", 1280, 720, (10, -5, overview_z), -90, -90))
        for name, width, height, position, yaw, pitch in specs:
            blueprint = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", 80), ("sensor_tick", 0)):
                blueprint.set_attribute(key, str(value))
            sensor = world.spawn_actor(blueprint, carla.Transform(
                carla.Location(*position), carla.Rotation(yaw=yaw, pitch=pitch)))
            owned.append(sensor)
            sensors[name] = queue.Queue()
            sensor.listen(sensors[name].put)
            logs[name] = (output / (name + ".encoder.log")).open("x")
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
                "-r", str(RATE), "-i", "pipe:0", "-an", "-c:v", "ffv1",
                str(output / (name + ".mkv"))], stdin=subprocess.PIPE, stderr=logs[name])
        for _ in range(20):
            world.tick()
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / "native-raw-actors.jsonl").open("x") as actor_file, \
                (output / "video_frames.jsonl").open("x") as video_file:
            for index, request in enumerate(requests):
                ego.apply_control(vehicle_control(ego, requests[min(index + 4, FRAMES - 1)], carla))
                other.apply_control(other_control(other, request["requested_other_vehicle_xyz_m"][0], carla))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                actor_file.write(json.dumps({
                    "frame": index, "native_frame": frame, "time_s": time_s,
                    "source_kind": "original_native", "request_frame": request["frame"],
                    "ego": actor_row(ego), "other_vehicle": actor_row(other),
                    "red_actor_id": red.id, "red_state": str(red.get_state()),
                    "arrow_actor_id": arrow.id, "arrow_state": str(arrow.get_state()),
                    "requested_phase": request["requested_phase"],
                    "directional_arrow_pixels_verified": False,
                    "signal_governs_ego_verified": False,
                    "other_traffic_lawfulness_verified": False,
                    "legal_verdict": None}, allow_nan=False) + "\n")
                for name, width, height, *_ in specs:
                    image = sensors[name].get(timeout=30)
                    while image.frame < frame:
                        image = sensors[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError("Camera/native frame join failed")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                video_file.write(json.dumps({"video_frame": index,
                                             "native_frame": frame, "time_s": time_s}) + "\n")
                frames += 1
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
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
                if actor.type_id.startswith("sensor.") and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"cleanup_error": str(exc)}
        if changed:
            try:
                restoration = restore(client, saved_world)
            except BaseException as exc:
                error = error or {"restore_error": str(exc)}
        (output / "native-capture-report.json").write_text(json.dumps({
            "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
            "config_sha256": digest(bundle / "config.json"),
            "requested_frames": FRAMES, "observed_frames": frames,
            "restoration": restoration, "error": error,
            "accepted": False, "delivery_ready": False,
            "legal_verdict": None}, indent=2) + "\n")
    if error:
        raise RuntimeError("C111603 original Native attempt failed; inspect capture report")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.bundle is None:
        selection = json.loads(Path("candidate-selection.json").read_text())
        suffix = selection["case_id"].split("__")[-1]
        args.bundle = Path("work") / selection["case_id"].rsplit("__", 1)[0] / "native" / "drafts" / suffix / selection["candidate_id"]
    if args.check:
        print(json.dumps(check(args.bundle)))
    else:
        if args.output is None:
            parser.error("--output required for original capture")
        capture(args.bundle, args.output, args.host, args.port)
