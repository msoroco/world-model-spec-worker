"""NRS 484B.407 Native source capture; --check is CPU-only.

The current returned site is diagnostic. Native capture requires a separately
reviewed and hash-bound site packet and is never run by this worker.
"""
import argparse
import hashlib
import json
import math
from contextlib import ExitStack, contextmanager
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import SIZES, source_cameras
from site_construction import load_site, spawned_occluder, validate_site
from u_turn_control import UTurnController

PREFIX = "testing__C129731__NRS-484B-407__motor_vehicle_driver__"
CASES = {PREFIX + feature + "__" + probe: (feature, probe)
         for feature in ("curve", "crest")
         for probe in ("short_of_500ft", "at_500ft", "beyond_500ft")}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_config(config, base_dir, diagnostic=False):
    case = config.get("selected_case_id")
    if (case not in CASES or config.get("law_id") != "NRS-484B-407"
            or config.get("cell_id") != "C129731"
            or config.get("actor") != "motor_vehicle_driver"):
        raise ValueError("Exact C129731 case identity required")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 55:
        raise ValueError("Exact 20 Hz, 55-second capture required")
    if config.get("required_atoms") != ["st.sight_distance"]:
        raise ValueError("Pinned sight-distance atom required")
    if config.get("source_packets") not in ([], None):
        raise ValueError("Unexpected observation adapter source packet")
    if not str(config.get("vehicle_blueprint_id", "")).startswith("vehicle."):
        raise ValueError("Exact motor-vehicle blueprint required")
    ref = config.get("site_source")
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise ValueError("Exact hashed site source required")
    path = Path(base_dir) / ref["path"]
    if not path.is_file() or _sha(path) != ref["sha256"]:
        raise ValueError("Site source missing or changed")
    site = validate_site(json.loads(path.read_text())) if diagnostic else load_site(path, ref["sha256"])
    if (site["feature"], site.get("probe")) != CASES[case]:
        raise ValueError("Selected feature/probe differs from sourced site")
    cameras = site.get("camera_poses")
    if not isinstance(cameras, dict) or set(cameras) != set(SIZES):
        raise ValueError("All four named source-camera poses required")
    for name, pose in cameras.items():
        if not isinstance(pose, list) or len(pose) != 6 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in pose):
            raise ValueError("Finite six-coordinate camera pose required: " + name)
    return site


def _transform(carla, xyz, yaw):
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(yaw=yaw))


def _camera_transform(carla, pose):
    return carla.Transform(carla.Location(x=pose[0], y=pose[1], z=pose[2]),
                           carla.Rotation(yaw=pose[3], pitch=pose[4], roll=pose[5]))


def _heading(a, b):
    return math.degrees(math.atan2(b[1]-a[1], b[0]-a[0]))


def _camera_frame(queue, frame):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError("Missing source camera frame " + str(frame)) from error
        if image.frame == frame:
            return image
        if image.frame > frame:
            raise ValueError("Source camera skipped requested frame " + str(frame))
    raise ValueError("Source camera frame join failed")


@contextmanager
def _vehicle(world, blueprint, pose, label):
    actor = world.try_spawn_actor(blueprint, pose)
    if actor is None:
        raise ValueError("Native vehicle spawn failed: " + label)
    try:
        yield actor
    finally:
        actor.destroy()


def _check_lane(world, carla, point, expected, label):
    waypoint = world.get_map().get_waypoint(carla.Location(x=point[0], y=point[1], z=point[2]),
                                            project_to_road=False)
    if waypoint is None or [waypoint.road_id, waypoint.lane_id] != expected:
        raise ValueError("Native road/lane differs from sourced approach: " + label)


def _other_control(carla, actor, stations, progress, target_speed=4.0):
    """Move an approaching car along ordered lane waypoints and brake near site."""
    pose = actor.get_transform()
    x, y = float(pose.location.x), float(pose.location.y)
    yaw = math.radians(float(pose.rotation.yaw))
    velocity = actor.get_velocity()
    speed = math.sqrt(sum(float(getattr(velocity, axis))**2 for axis in "xyz"))
    if any(not math.isfinite(v) for v in (x, y, yaw, speed)):
        raise ValueError("Finite approaching-vehicle feedback required")
    route = [row["xyz_m"] for row in reversed(stations)]
    while progress < len(route)-1 and math.dist((x, y), route[progress][:2]) < 4:
        progress += 1
    target = route[progress]
    distance = math.dist((x, y), target[:2])
    error = (math.atan2(target[1]-y, target[0]-x)-yaw+math.pi) % (2*math.pi)-math.pi
    curvature = 2*math.sin(error)/max(distance, 4)
    steer = max(-1., min(1., -math.atan(2.8*curvature)/math.radians(35)))
    near_site = math.dist((x, y), route[-1][:2]) <= max(4, speed*speed/8)
    control = carla.VehicleControl()
    control.steer = steer
    control.throttle = 0 if near_site else max(0., min(.5, .18+.16*(target_speed-speed)))
    control.brake = 1. if near_site else min(.35, max(0., .25*(speed-target_speed)))
    actor.apply_control(control)
    return progress, {"speed_mps": speed, "target_index": progress, "near_site_brake": near_site,
                      "steer": steer, "throttle": control.throttle, "brake": control.brake}


def _actor_row(actor, mapping):
    pose, speed = actor.get_transform(), actor.get_velocity()
    waypoint = mapping.get_waypoint(pose.location, project_to_road=False)
    return {"id": actor.id, "location_xyz_m": [float(getattr(pose.location, a)) for a in "xyz"],
            "yaw_deg": float(pose.rotation.yaw),
            "velocity_xyz_mps": [float(getattr(speed, a)) for a in "xyz"],
            "road_lane": None if waypoint is None else [waypoint.road_id, waypoint.lane_id]}


def _body_vertices(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    return [[float(getattr(vertex, axis)) for axis in "xyz"] for vertex in vertices]


def capture(args, config, site):
    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Materialize the exact construction through runtime.py capture")
    if site["source_status"] != "reviewed_candidate":
        raise ValueError("Diagnostic site cannot be captured")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot

    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = snapshot(client)
    world = client.get_world()
    encoders, captured, helper, errors = {}, 0, None, []
    try:
        (output/"curve_context.json").write_text(json.dumps({
            "site_source_sha256": config["site_source"]["sha256"],
            "feature": site["feature"], "turn_site_xyz_m": site["turn_site_xyz_m"],
            "incoming_lanes": site["incoming_lanes"],
            "visibility_proxy_only": True}, allow_nan=False)+"\n")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        if world.get_map().name != site["map_name"]:
            raise ValueError("Native map differs from reviewed curve/crest source")
        blueprint = world.get_blueprint_library().find(config["vehicle_blueprint_id"])
        if blueprint is None or not blueprint.id.startswith("vehicle."):
            raise ValueError("Motor-vehicle blueprint unavailable")
        route = site["u_turn_route_xyz_m"]
        ego_pose = _transform(carla, route[0], _heading(route[0], route[1]))
        _check_lane(world, carla, route[0], site["ego_road_lane"], "ego")
        with ExitStack() as actors:
            ego = actors.enter_context(_vehicle(world, blueprint, ego_pose, "ego"))
            approaching = {}
            for name, lane in site["incoming_lanes"].items():
                stations = lane["stations"]
                far, next_point = stations[-1]["xyz_m"], stations[-2]["xyz_m"]
                _check_lane(world, carla, far, [lane["road_id"], lane["lane_id"]], name)
                pose = _transform(carla, far, _heading(far, next_point))
                approaching[name] = actors.enter_context(_vehicle(world, blueprint, pose, name))
            actors.enter_context(spawned_occluder(world, carla, site))
            camera_poses = {name: _camera_transform(carla, pose)
                            for name, pose in site["camera_poses"].items()}
            with source_cameras(world, ego, camera_poses) as sensors:
                queues = {name: Queue() for name in SIZES}
                for name, sensor in sensors.items():
                    sensor.listen(lambda image, name=name: queues[name].put(image))
                with ExitStack() as resources:
                    for name, (width, height) in SIZES.items():
                        encoders[name] = resources.enter_context(FFV1Writer(output/(name+".mkv"), width, height))
                    mapping = resources.enter_context(FrameMap(output/"video_frames.jsonl"))
                    motion = resources.enter_context((output/"motion_history.jsonl").open("x", buffering=1))
                    turn_history = resources.enter_context((output/"turn_history.jsonl").open("x", buffering=1))
                    helper = PipelineCapture(client, ego, output, config["selected_case_id"],
                                             required_observations=config["required_atoms"])
                    turn = UTurnController(route)
                    progress = {name: 1 for name in approaching}
                    try:
                        for index in range(config["rate_hz"]*config["duration_s"]):
                            ego_command = turn.step(carla, ego, index)
                            other_commands = {}
                            for name, other in approaching.items():
                                progress[name], other_commands[name] = _other_control(
                                    carla, other, site["incoming_lanes"][name]["stations"], progress[name], target_speed=5.0)
                            world.tick()
                            snap = world.get_snapshot()
                            for name in SIZES:
                                image = _camera_frame(queues[name], snap.frame)
                                encoders[name].write(bytes(image.raw_data))
                            helper.capture(snap.frame, snap.timestamp.elapsed_seconds)
                            row = mapping.append(snap.frame, snap.timestamp.elapsed_seconds,
                                                 cameras=list(SIZES))
                            motion.write(json.dumps({"native_frame": snap.frame,
                                "video_frame": row["video_frame"], "ego": _actor_row(ego, world.get_map()),
                                "approaches": {name: _actor_row(actor, world.get_map()) for name, actor in approaching.items()},
                                "ego_controller": ego_command, "approach_controllers": other_commands,
                                "site_source_sha256": config["site_source"]["sha256"]},
                                allow_nan=False)+"\n")
                            turn_history.write(json.dumps({"frame": snap.frame,
                                "time_s": snap.timestamp.elapsed_seconds,
                                "body_vertices_m": _body_vertices(ego),
                                "heading_deg": float(ego.get_transform().rotation.yaw)},
                                allow_nan=False)+"\n")
                            captured += 1
                    finally:
                        helper.close()
                        helper = None
    except BaseException as error:
        errors.append(str(error))
        raise
    finally:
        if helper is not None:
            helper.close(confirmed=False)
        restoration = restore(client, saved)
        if not errors:
            seal_capture(output, frames=captured, restoration=restoration, errors=[],
                         encoder_exit_codes={name: encoders[name].exit_code for name in SIZES},
                         context={"physical_acceptance_claimed": False,
                                  "site_source_sha256": config["site_source"]["sha256"],
                                  "driver_visibility_unverified": True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text())
    site = validate_config(config, config_path.parent, diagnostic=args.check)
    if args.check:
        print(json.dumps({"case_id": config["selected_case_id"], "feature": site["feature"],
                          "probe": site["probe"], "camera_names": sorted(SIZES),
                          "frames": config["rate_hz"]*config["duration_s"],
                          "site_status": site["source_status"], "carla_started": False}))
    else:
        if not args.output_dir:
            raise ValueError("Native output directory required")
        capture(args, config, site)


if __name__ == "__main__":
    main()
