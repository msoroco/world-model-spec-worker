"""Unaccepted CARLA attempt for the C109137 stripe/adjoining-road pair."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback
import xml.etree.ElementTree as ET

from check import check
from build import FRAMES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def body(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    vertices = actor.bounding_box.get_world_vertices(transform)
    return {
        "actor_id": actor.id, "blueprint": actor.type_id,
        "center_native_xyz_m": [transform.location.x, transform.location.y,
                                transform.location.z],
        "yaw_deg": transform.rotation.yaw,
        "velocity_native_xyz_mps": [velocity.x, velocity.y, velocity.z],
        "speed_mps": math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
        "body_native_xyz_m": [[p.x, p.y, p.z] for p in vertices],
        "light_state": int(actor.get_light_state()) if
            actor.type_id.startswith("vehicle.") else None}


def control_for(ego, target_xy, target_speed, carla):
    pose = ego.get_transform()
    velocity = ego.get_velocity()
    current = math.hypot(velocity.x, velocity.y)
    desired = math.degrees(math.atan2(
        target_xy[1] - pose.location.y, target_xy[0] - pose.location.x))
    error = (desired - pose.rotation.yaw + 180) % 360 - 180
    if target_speed <= .1:
        return carla.VehicleControl(throttle=0, brake=1, steer=0)
    return carla.VehicleControl(
        throttle=max(0, min(.7, .35 + .12 * (target_speed - current))),
        brake=0, steer=max(-.8, min(.8, error / 40)))


def capture(bundle, output, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    checked = check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requests = [json.loads(line) for line in
                (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = client.get_world()
    saved = snapshot(client)
    if prior.get_settings().synchronous_mode or any(
            actor.type_id.startswith(("vehicle.", "walker.", "sensor."))
            for actor in prior.get_actors()):
        raise RuntimeError("Exclusive idle asynchronous CARLA world required")
    output.mkdir(parents=True, exist_ok=False)
    owned, cameras, encoders, logs = [], {}, {}, {}
    changed, frames, error, restored, pipeline = False, 0, None, None, None
    road_readback = None
    try:
        world = client.generate_opendrive_world(
            (bundle / "zone-adjoining.xodr").read_text(),
            carla.OpendriveGenerationParameters(
                vertex_distance=.25, max_road_length=50, wall_height=0,
                additional_width=0, smooth_junctions=False,
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
        surveyed = {}
        for name, x, y, road_id, lane_id in (
                ("ego_approach", 20, -1.75, 217, -1),
                ("stripe_region", 48, -1.75, 217, -1),
                ("oncoming", 80, 1.75, 219, 1),
                ("adjoining", 55.25, 15, 218, -1)):
            wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=1),
                                      project_to_road=False, lane_type=carla.LaneType.Any)
            surveyed[name] = None if wp is None else {
                "road_id": wp.road_id, "lane_id": wp.lane_id,
                "lane_type": "driving" if wp.lane_type == carla.LaneType.Driving else "other"}
            if wp is None or wp.road_id != road_id or wp.lane_id != lane_id or \
                    wp.lane_type != carla.LaneType.Driving:
                raise RuntimeError("Generated main/adjoining lane readback differs: " + name)
        for name, road_id, station in (("straight_connector", 220, 2.5),
                                       ("turn_connector", 221, 2.5)):
            wp = mapping.get_waypoint_xodr(road_id, -1, station)
            surveyed[name] = None if wp is None else {
                "road_id": wp.road_id, "lane_id": wp.lane_id,
                "lane_type": "driving" if wp.lane_type == carla.LaneType.Driving else "other"}
            if wp is None or wp.road_id != road_id or wp.lane_id != -1 or \
                    wp.lane_type != carla.LaneType.Driving:
                raise RuntimeError("Generated junction connector lane readback differs: " + name)
        generated = mapping.to_opendrive()
        generated_xml = ET.fromstring(generated)
        generated_roads = {r.get("id"): r for r in generated_xml.findall("./road")}
        generated_junction = generated_xml.find("./junction[@id='1']")
        connections = set() if generated_junction is None else {
            (c.get("incomingRoad"), c.get("connectingRoad"))
            for c in generated_junction.findall("./connection")}
        if (set(generated_roads) != {"217", "218", "219", "220", "221"} or
                {("217", "220"), ("217", "221"), ("219", "220")} - connections or
                generated_roads["220"].get("junction") != "1" or
                generated_roads["221"].get("junction") != "1"):
            raise RuntimeError("Generated highway/adjoining junction topology absent")
        road_readback = surveyed
        library = world.get_blueprint_library()
        bp = library.find("vehicle.tesla.model3")
        bp.set_attribute("role_name", "c109137_ego")
        ego = world.try_spawn_actor(
            bp, carla.Transform(carla.Location(x=10, y=-1.75, z=1.5)))
        if ego is None:
            raise RuntimeError("Ego spawn failed")
        owned.append(ego)
        oncoming = world.try_spawn_actor(
            bp, carla.Transform(carla.Location(x=135, y=1.75, z=1.5),
                                carla.Rotation(yaw=180)))
        following = world.try_spawn_actor(
            bp, carla.Transform(carla.Location(x=0, y=-1.75, z=1.5)))
        if oncoming is None or following is None:
            raise RuntimeError("Comparison traffic spawn failed")
        owned.extend((oncoming, following))
        elevated = cfg["camera_policy"] == "elevated"
        specs = (("overview", 1280, 720, 90 if elevated else 80,
                  (50, -25, 50 if elevated else 35), -70 if elevated else -60),
                 ("forward", 1280, 720, 90, (1, 0, 1.5), 0),
                 ("stripe_side", 1280, 720, 80, (52, -14, 8), -25))
        for name, width, height, fov, xyz, pitch in specs:
            camera_bp = library.find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", fov), ("sensor_tick", 0)):
                camera_bp.set_attribute(key, str(value))
            camera = world.spawn_actor(
                camera_bp,
                carla.Transform(carla.Location(*xyz), carla.Rotation(pitch=pitch)),
                attach_to=ego if name == "forward" else None)
            owned.append(camera)
            cameras[name] = queue.Queue()
            camera.listen(cameras[name].put)
            logs[name] = (output / (name + ".encoder.log")).open("x")
            encoders[name] = subprocess.Popen(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
                 "-r", "20", "-i", "pipe:0", "-an", "-c:v", "ffv1",
                 str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=logs[name])
        write_new(output / "native-map-readback.json", {
            "source_kind": "original_native",
            "road_sha256": sha(bundle / "zone-adjoining.xodr"),
            "native_map_sha256": hashlib.sha256(generated.encode()).hexdigest(),
            "lane_readback": surveyed,
            "adjoining_connection_readback": True,
            "ego_actor_id": ego.id, "oncoming_actor_id": oncoming.id,
            "following_actor_id": following.id,
            "zone_legally_designated": False, "legal_verdict": None})
        for _ in range(20):
            world.tick()
        pipeline = PipelineCapture(client, ego, output, cfg["case_id"], visibility=False)
        start = world.get_snapshot().timestamp.elapsed_seconds
        left = carla.VehicleLightState.LeftBlinker
        with (output / "native-raw-actors.jsonl").open("x") as actors, \
             (output / "video_frames.jsonl").open("x") as videos:
            for i, request in enumerate(requests):
                desired = requests[min(i + 5, len(requests) - 1)]["requested_ego_xy_m"]
                ego.apply_control(control_for(ego, desired, request["requested_speed_mps"], carla))
                ego.set_light_state(left if request["requested_left_indicator"]
                                    else carla.VehicleLightState.NONE)
                oncoming.set_target_velocity(carla.Vector3D(x=-4, y=0, z=0))
                following.set_target_velocity(carla.Vector3D(x=2, y=0, z=0))
                frame = world.tick()
                t = world.get_snapshot().timestamp.elapsed_seconds - start
                wp = mapping.get_waypoint(ego.get_transform().location,
                                          project_to_road=False, lane_type=carla.LaneType.Any)
                row = {
                    "frame": i, "native_frame": frame, "time_s": t,
                    "source_kind": "original_native",
                    "requested_ego_xy_m": request["requested_ego_xy_m"],
                    "requested_speed_mps": request["requested_speed_mps"],
                    "requested_left_indicator": request["requested_left_indicator"],
                    "observed_left_indicator": bool(ego.get_light_state() & left),
                    "ego": body(ego), "oncoming": body(oncoming),
                    "following": body(following),
                    "observed_road_id": None if wp is None else wp.road_id,
                    "observed_lane_id": None if wp is None else wp.lane_id,
                    "zone_legally_designated": False,
                    "physical_stripe_crossing_observed": None,
                    "traffic_impediment_reviewed": False, "legal_verdict": None}
                actors.write(json.dumps(row, allow_nan=False) + "\n")
                pipeline.capture(frame, t, extra={"c109137_zone": row})
                for name, width, height, _, _, _ in specs:
                    image = cameras[name].get(timeout=30)
                    while image.frame < frame:
                        image = cameras[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError("Native/video frame join failed")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                videos.write(json.dumps({"video_frame": i, "native_frame": frame,
                                         "time_s": t}) + "\n")
                frames += 1
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        if pipeline is not None:
            try:
                pipeline.close(confirmed=error is None)
            except BaseException as exc:
                error = error or {"capture_close_error": str(exc)}
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
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {"restore_error": str(exc)}
        write_new(output / "native-capture-report.json", {
            "case_id": checked["case_id"], "candidate_id": checked["candidate_id"],
            "config_sha256": sha(bundle / "config.json"), "requested_frames": FRAMES,
            "observed_frames": frames, "road_readback": road_readback,
            "restoration": restored, "error": error,
            "accepted": False, "delivery_ready": False,
            "zone_legally_designated": False, "legal_verdict": None})
    if error:
        raise RuntimeError("C109137 Native attempt failed; see capture report")


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
            raise ValueError("Original Native output directory required")
        capture(args.bundle, args.output_dir, args.host, args.port)
