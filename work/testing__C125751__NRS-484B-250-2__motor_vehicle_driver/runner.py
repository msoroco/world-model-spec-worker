"""Native two-signal median crossing capture; --check is CPU-only."""
import argparse
import json
import math
from contextlib import ExitStack, contextmanager
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import SIZES, source_cameras
from capture_sources import record_frame, source_contexts
from native_pair import construct_pair
from route_control import steering_command, validate_route
from signal_control import find_governing_signal, SignalPairControl
from site_packet import verify_site_packet
from stop_control import StopApproach, front_speed
from yield_controller import apply_speed_control, body_in_crossing

PREFIX = "testing__C125751__NRS-484B-250-2__motor_vehicle_driver__"
TARGETS = {PREFIX + "signal_operative": ("Green", "Red"),
           PREFIX + "signal_off": ("Off", "Off")}
POSES = ("ego_approach", "ego_entry", "other_approach", "other_entry")


def _pose(value, length, label):
    if not isinstance(value, list) or len(value) != length or any(
            type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError("Finite " + label + " pose required")
    return value


def validate_config(config, base_dir=Path.cwd()):
    case = config.get("selected_case_id")
    if (case not in TARGETS or config.get("law_id") != "NRS-484B-250-2"
            or config.get("cell_id") != "C125751"):
        raise ValueError("Exact C125751 signal case required")
    if config.get("target_signal_state") != TARGETS[case][0]:
        raise ValueError("Signal case and requested ego Native state differ")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 55:
        raise ValueError("Planned 20 Hz, 55-second capture required")
    if not isinstance(config.get("recording_description"), dict) or not isinstance(config.get("required_atoms"), list):
        raise ValueError("Recording description and pinned Core atoms required")
    site = config.get("site")
    if not isinstance(site, dict) or not site.get("native_map_name") or type(site.get("crossing_id")) is not int:
        raise ValueError("Reviewed Native median site required")
    if site.get("diagnostic_site_only") is True:
        raise ValueError("Synthetic diagnostic site cannot be used for Native capture")
    for key in ("polygon_source", "approach_geometry_source", "device_inventory_source",
                "camera_plan_source"):
        if not isinstance(site.get(key), str) or not site[key].strip():
            raise ValueError("Missing reviewed site source: " + key)
    heads = site.get("head_geometry_sources")
    if not isinstance(heads, dict) or set(heads) != {"ego", "other"} or any(
            not isinstance(value, str) or not value.strip() for value in heads.values()):
        raise ValueError("Two source-grounded signal-head geometry plans required")
    lanes = site.get("expected_approach_lanes")
    if not isinstance(lanes, dict) or set(lanes) != {"ego", "other"} or any(
            not isinstance(pair, list) or len(pair) != 2 or any(type(x) is not int for x in pair)
            for pair in lanes.values()) or lanes["ego"] == lanes["other"]:
        raise ValueError("Distinct reviewed approach road/lane identities required")
    if site.get("ego_highway_id") == site.get("other_highway_id") or any(
            site.get(key) is None for key in ("ego_highway_id", "other_highway_id")):
        raise ValueError("Distinct sourced highways required")
    polygon = site.get("crossing_polygon_xy_m")
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError("Sourced crossing polygon required")
    for vertex in polygon:
        _pose(vertex, 2, "crossing vertex")
    for key in POSES:
        _pose(site.get(key), 4, key)
    cameras = site.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(SIZES):
        raise ValueError("All four named source-camera poses required")
    for name, pose in cameras.items():
        _pose(pose, 6, name + " camera")
    routes = site.get("routes")
    if not isinstance(routes, dict) or set(routes) != {"ego", "other"}:
        raise ValueError("Two reviewed crossing routes required")
    for role in ("ego", "other"):
        validate_route(routes[role], site[role + "_approach"],
                       site[role + "_entry"], role, polygon)
    references = site.get("selected_stop_references")
    if not isinstance(references, dict) or set(references) != {"ego", "other"}:
        raise ValueError("Reviewed subsection-4 stop reference required for each approach")
    for party, reference in references.items():
        if not isinstance(reference, dict) or reference.get("kind") not in (
                "marked_stop_line", "near_side_crosswalk", "nearest_view_point"):
            raise ValueError("Source-selected stop reference required: " + party)
        if not reference.get("geometry_source") or not reference.get("reference_review_source"):
            raise ValueError("Stop reference provenance required: " + party)
        segment = reference.get("segment_xy_m")
        if not isinstance(segment, list) or len(segment) != 2:
            raise ValueError("Source-selected stop reference segment required: " + party)
        for point in segment:
            _pose(point, 2, party + " stop reference endpoint")
    for key in ("ego_target_speed_mps", "other_target_speed_mps"):
        speed = config.get(key)
        if type(speed) not in (int, float) or not math.isfinite(speed) or not 0 < speed <= 20:
            raise ValueError("Positive finite " + key + " required")
    release = config.get("other_release_frame")
    if type(release) is not int or not 0 <= release < 1100:
        raise ValueError("Valid other release frame required")
    verify_site_packet(config, base_dir)
    return config


def _transform(carla, pose):
    return carla.Transform(carla.Location(x=pose[0], y=pose[1], z=pose[2]),
                           carla.Rotation(yaw=pose[3],
                                          pitch=pose[4] if len(pose) > 4 else 0,
                                          roll=pose[5] if len(pose) > 5 else 0))


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
def _spawn_ego(world, blueprint, pose):
    actor = world.try_spawn_actor(blueprint, pose)
    if actor is None:
        raise ValueError("Ego Native spawn failed")
    try:
        yield actor
    finally:
        actor.destroy()


def capture(args, config):
    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Use runtime.py capture to materialize exact construction first")
    site = config["site"]
    reviewed = verify_site_packet(config, Path(args.config).parent)
    if reviewed["diagnostic_only"]:
        raise ValueError("Diagnostic site sources cannot be used for Native capture")
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot as save_world
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = save_world(client)
    world = client.get_world()
    encoders, captured, errors, helper = {}, 0, [], None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        if world.get_map().name != site["native_map_name"]:
            raise ValueError("Native map differs from reviewed signal site")
        transforms = {key: _transform(carla, site[key]) for key in POSES}
        blueprint = world.get_blueprint_library().filter("vehicle.*")[0]
        with _spawn_ego(world, blueprint, transforms["ego_approach"]) as ego:
            with construct_pair(world, site, transforms, blueprint) as (plan, other):
                ego_lane, other_lane = (plan["approaches"][role] for role in ("ego", "other"))
                for role, approach in (("ego", ego_lane), ("other", other_lane)):
                    if [approach["road_id"], approach["lane_id"]] != site["expected_approach_lanes"][role]:
                        raise ValueError("Native approach road/lane differs from reviewed site: " + role)
                ego_light = find_governing_signal(world, ego_lane["road_id"], ego_lane["lane_id"])
                other_light = find_governing_signal(world, other_lane["road_id"], other_lane["lane_id"])
                ego_state, other_state = TARGETS[config["selected_case_id"]]
                with SignalPairControl(world, ego_light, other_light,
                                       carla.TrafficLightState, ego_state, other_state):
                    contexts = source_contexts(site, plan, ego_light, other_light)
                    for context in contexts.values():
                        context["site_review_sha256"] = reviewed["packet_sha256"]
                    for name, value in contexts.items():
                        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
                    camera_poses = {name: _transform(carla, pose) for name, pose in site["cameras"].items()}
                    with source_cameras(world, ego, camera_poses) as sensors:
                        queues = {name: Queue() for name in SIZES}
                        for name, sensor in sensors.items():
                            sensor.listen(lambda image, name=name: queues[name].put(image))
                        with ExitStack() as stack:
                            for name, (width, height) in SIZES.items():
                                encoders[name] = stack.enter_context(FFV1Writer(output / (name + ".mkv"), width, height))
                            mapping = stack.enter_context(FrameMap(output / "video_frames.jsonl"))
                            crossing = stack.enter_context((output / "crossing_history.jsonl").open("x", buffering=1))
                            signals = stack.enter_context((output / "signal_history.jsonl").open("x", buffering=1))
                            stops = stack.enter_context((output / "stop_history.jsonl").open("x", buffering=1))
                            controls = stack.enter_context((output / "controller_history.jsonl").open("x", buffering=1))
                            helper = PipelineCapture(client, ego, output, config["selected_case_id"],
                                                     required_observations=config["required_atoms"])
                            try:
                                other_entered = False
                                progress = {"ego": 1, "other": 1}
                                stop_controllers = {role: StopApproach(
                                    site["selected_stop_references"][role]["segment_xy_m"])
                                    for role in ("ego", "other")}
                                for index in range(1100):
                                    other_inside = body_in_crossing(other, site["crossing_polygon_xy_m"])
                                    other_entered = other_entered or other_inside
                                    decisions = {}
                                    for role, actor in (("ego", ego), ("other", other)):
                                        pose = actor.get_transform()
                                        steer, progress[role] = steering_command(
                                            float(pose.location.x), float(pose.location.y),
                                            float(pose.rotation.yaw), site["routes"][role], progress[role])
                                        front, speed, forward = front_speed(actor)
                                        release_allowed = other_entered if role == "ego" else index >= config["other_release_frame"]
                                        stop_decision = stop_controllers[role].step(front, speed, forward, release_allowed)
                                        decisions[role] = {"steer": steer, "stop": stop_decision}
                                    ego_control = apply_speed_control(carla, ego, config["ego_target_speed_mps"],
                                                                      decisions["ego"]["stop"]["hold"],
                                                                      decisions["ego"]["steer"])
                                    other_control = apply_speed_control(carla, other, config["other_target_speed_mps"],
                                                                        decisions["other"]["stop"]["hold"],
                                                                        decisions["other"]["steer"])
                                    world.tick()
                                    snap = world.get_snapshot()
                                    for name in SIZES:
                                        image = _camera_frame(queues[name], snap.frame)
                                        encoders[name].write(bytes(image.raw_data))
                                    helper.capture(snap.frame, snap.timestamp.elapsed_seconds)
                                    record_frame(mapping, crossing, signals, stops, snap, world.get_map(),
                                                 ego, other, ego_light, other_light, plan, ego_state, other_state)
                                    controls.write(json.dumps({"frame": snap.frame,
                                        "time_s": snap.timestamp.elapsed_seconds,
                                        "other_inside_before_tick": other_inside,
                                        "other_entered_once": other_entered,
                                        "ego_control": ego_control, "other_control": other_control,
                                        "route_target_index": progress.copy(),
                                        "steering": decisions}, allow_nan=False) + "\n")
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
                                  "head_pixel_review_pending": True,
                                  "site_review_sha256": reviewed["packet_sha256"]})


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
        print(json.dumps({"case_id": config["selected_case_id"], "frames": 1100,
                          "camera_names": sorted(SIZES), "signal_states": TARGETS[config["selected_case_id"]],
                          "carla_started": False}))
    else:
        if not args.output_dir:
            raise ValueError("Native output directory required")
        capture(args, config)


if __name__ == "__main__":
    main()
