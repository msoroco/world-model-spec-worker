"""Native subsection-2 median entry capture; --check stays CPU-only."""
import argparse
import json
import math
from contextlib import ExitStack, contextmanager
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import SIZES, source_cameras
from capture_sources import record_crossing_sample, road_geometry
from native_pair import construct_pair
from route_control import steering_command, validate_route
from site_packet import verify_site_packet
from yield_controller import apply_speed_control, body_in_crossing, near_time_entry_hold

CASE = "testing__C125714__NRS-484B-250-2__motor_vehicle_driver__source_verified_other_right_near_time"
POSES = ("ego_approach", "ego_entry", "other_approach", "other_entry")


def _numbers(value, length, label):
    if not isinstance(value, list) or len(value) != length or any(
            type(item) not in (int, float) or not math.isfinite(item) for item in value):
        raise ValueError("Finite " + label + " required")
    return value


def validate_config(config, base_dir=Path.cwd()):
    if config.get("selected_case_id") != CASE or config.get("law_id") != "NRS-484B-250-2" or config.get("cell_id") != "C125714":
        raise ValueError("Exact right-hand median-entry case required")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 55:
        raise ValueError("Planned 20 Hz, 55-second capture required")
    if not isinstance(config.get("required_atoms"), list) or not isinstance(config.get("recording_description"), dict):
        raise ValueError("Pinned atoms and recording description required")
    physical = config.get("physical_completion", {})
    if "road_geometry.json" not in physical.get("context_sources", []) or physical.get("body_key") != "ego_vertices_m":
        raise ValueError("Physical assessor must read original body and sourced crossing")
    site = config.get("site")
    if not isinstance(site, dict) or not site.get("native_map_name") or type(site.get("crossing_id")) is not int:
        raise ValueError("Reviewed Native median site required")
    for key in ("polygon_source", "entrance_source", "median_spacing_source",
                "device_review_source", "statutory_crossing_review_source",
                "approach_geometry_source"):
        if not isinstance(site.get(key), str) or not site[key].strip():
            raise ValueError("Missing reviewed site source: " + key)
    if site.get("same_statutory_crossing_reviewed") is not True:
        raise ValueError("Statutory crossing identity review required")
    if site.get("ego_highway_id") == site.get("other_highway_id") or any(
            site.get(key) is None for key in ("ego_highway_id", "other_highway_id")):
        raise ValueError("Distinct sourced highways required")
    polygon = site.get("crossing_polygon_xy_m")
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError("Crossing polygon required")
    for vertex in polygon:
        _numbers(vertex, 2, "crossing vertex")
    for key in POSES:
        _numbers(site.get(key), 4, key + " pose")
    routes = site.get("routes")
    if not isinstance(routes, dict) or set(routes) != {"ego", "other"}:
        raise ValueError("Two reviewed crossing routes required")
    for role in ("ego", "other"):
        validate_route(routes[role], site[role + "_approach"],
                       site[role + "_entry"], role, polygon)
    cameras = site.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(SIZES):
        raise ValueError("All four named camera poses required")
    for name, pose in cameras.items():
        _numbers(pose, 6, name + " camera pose")
    for key in ("ego_target_speed_mps", "other_target_speed_mps"):
        value = config.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 20:
            raise ValueError("Positive finite " + key + " required")
    if type(config.get("other_release_frame")) is not int or not 0 <= config["other_release_frame"] < 1100:
        raise ValueError("Valid other release frame required")
    verify_site_packet(config, base_dir)
    return config


def _transform(carla, pose):
    return carla.Transform(carla.Location(x=pose[0], y=pose[1], z=pose[2]),
                           carla.Rotation(yaw=pose[3],
                                          pitch=pose[4] if len(pose) > 4 else 0,
                                          roll=pose[5] if len(pose) > 5 else 0))


def _sensor_frame(queue, frame):
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
def _spawn_ego(world, blueprint, pose):
    ego = world.try_spawn_actor(blueprint, pose)
    if ego is None:
        raise ValueError("Ego Native spawn failed")
    try:
        yield ego
    finally:
        ego.destroy()


def capture(args, config):
    if config["site"].get("diagnostic_site_only") is True:
        raise ValueError("Synthetic diagnostic site cannot be used for Native capture")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot as save_world

    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Use runtime.py capture to materialize exact construction first")
    site = config["site"]
    reviewed = verify_site_packet(config, Path(args.config).parent)
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = save_world(client)
    world = client.get_world()
    encoders, frames, errors, helper = {}, 0, [], None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        world_map = world.get_map()
        transforms = {key: _transform(carla, site[key]) for key in POSES}
        blueprint = world.get_blueprint_library().filter("vehicle.*")[0]
        with _spawn_ego(world, blueprint, transforms["ego_approach"]) as ego:
            with construct_pair(world, site, transforms, blueprint) as (plan, other):
                entrance_lanes = {tuple(pair) for pair in reviewed["device_review"]["entrance_road_lanes"]}
                native_lanes = {(plan["approaches"][role]["road_id"],
                                 plan["approaches"][role]["lane_id"]) for role in ("ego", "other")}
                if not native_lanes <= entrance_lanes:
                    raise ValueError("Native participant entrance absent from reviewed device inventory")
                geometry = road_geometry({"device_inventory_source": site["device_review_source"],
                                          "device_review": reviewed["device_review"]}, plan)
                (output / "road_geometry.json").write_text(json.dumps(geometry, indent=2) + "\n")
                camera_poses = {name: _transform(carla, pose) for name, pose in site["cameras"].items()}
                with source_cameras(world, ego, camera_poses) as sensors:
                    queues = {name: Queue() for name in SIZES}
                    for name, sensor in sensors.items():
                        sensor.listen(lambda image, name=name: queues[name].put(image))
                    with ExitStack() as stack:
                        for name, (width, height) in SIZES.items():
                            encoders[name] = stack.enter_context(FFV1Writer(output / (name + ".mkv"), width, height))
                        frame_map = stack.enter_context(FrameMap(output / "video_frames.jsonl"))
                        history = stack.enter_context((output / "crossing_history.jsonl").open("x", buffering=1))
                        controls = stack.enter_context((output / "controller_history.jsonl").open("x", buffering=1))
                        helper = PipelineCapture(client, ego, output, config["selected_case_id"],
                                                 required_observations=config["required_atoms"])
                        try:
                            entered_once = False
                            progress = {"ego": 1, "other": 1}
                            for i in range(1100):
                                other_inside = body_in_crossing(other, site["crossing_polygon_xy_m"])
                                hold, entered_once = near_time_entry_hold(other_inside, entered_once)
                                decisions = {}
                                for role, actor in (("ego", ego), ("other", other)):
                                    pose = actor.get_transform()
                                    steer, progress[role] = steering_command(
                                        float(pose.location.x), float(pose.location.y),
                                        float(pose.rotation.yaw), site["routes"][role], progress[role])
                                    decisions[role] = {"steer": steer}
                                ego_decision = apply_speed_control(carla, ego, config["ego_target_speed_mps"],
                                                                   hold, decisions["ego"]["steer"])
                                other_decision = apply_speed_control(carla, other, config["other_target_speed_mps"],
                                                                     i < config["other_release_frame"],
                                                                     decisions["other"]["steer"])
                                world.tick()
                                snap = world.get_snapshot()
                                for name in SIZES:
                                    image = _sensor_frame(queues[name], snap.frame)
                                    encoders[name].write(bytes(image.raw_data))
                                helper.capture(snap.frame, snap.timestamp.elapsed_seconds)
                                record_crossing_sample(frame_map, history, snap, world_map, ego, other, plan)
                                controls.write(json.dumps({"frame": snap.frame,
                                    "time_s": snap.timestamp.elapsed_seconds,
                                    "other_inside_before_tick": other_inside,
                                    "other_entered_once": entered_once,
                                    "ego_control": ego_decision, "other_control": other_decision,
                                    "route_target_index": progress.copy(),
                                    "steering": decisions}, allow_nan=False) + "\n")
                                frames += 1
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
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: encoders[name].exit_code for name in SIZES},
                         context={"site_review_sha256": reviewed["packet_sha256"],
                                  "physical_acceptance_claimed": False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = validate_config(json.loads(Path(args.config).read_text()), Path(args.config).parent)
    if args.check:
        print(json.dumps({"case_id": CASE, "planned_frames": 1100,
                          "named_source_cameras": list(SIZES), "carla_started": False,
                          "cpu_check_passed": True, "physical_acceptance_claimed": False}))
        return
    if not args.output_dir:
        raise ValueError("--output-dir required for Native capture")
    capture(args, config)


if __name__ == "__main__":
    main()
