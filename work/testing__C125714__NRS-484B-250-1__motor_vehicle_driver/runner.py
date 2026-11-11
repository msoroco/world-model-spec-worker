"""Native median precedence candidate capture; CPU --check never imports CARLA."""
import argparse
import json
import math
from contextlib import ExitStack, contextmanager
from pathlib import Path
from queue import Empty, Queue

from camera_encoder import FFV1Writer
from camera_setup import SIZES, source_cameras
from capture_sources import record_crossing_sample
from native_crossing import construct_crossing_candidate
from site_packet import verify_site_packet

CASE = "testing__C125714__NRS-484B-250-1__motor_vehicle_driver__source_verified_precedence"
ENTRY_ORDER_CASES = {
    CASE: True,
    "testing__C125714__NRS-484B-250-1__motor_vehicle_driver__source_verified_advance": True,
    "testing__C125714__NRS-484B-250-1__motor_vehicle_driver__source_verified_other_later": False,
}
CAMERAS = tuple(SIZES)
POSES = ("ego_approach", "ego_entry", "other_approach", "other_entry")


def _numbers(values, size, label):
    if not isinstance(values, list) or len(values) != size or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError("Finite " + label + " required")
    return values


def validate_config(config, base_dir=Path.cwd()):
    case_id = config.get("selected_case_id")
    if case_id not in ENTRY_ORDER_CASES or config.get("law_id") != "NRS-484B-250-1" or config.get("cell_id") != "C125714":
        raise ValueError("Exact median entry-order case required")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 55:
        raise ValueError("Planned 20 Hz, 55-second capture required")
    if config.get("expected_other_enters_before_ego") is not ENTRY_ORDER_CASES[case_id]:
        raise ValueError("Selected case entry-order target required")
    if not isinstance(config.get("required_atoms"), list):
        raise ValueError("Pinned Core required_atoms list required")
    if not isinstance(config.get("recording_description"), dict):
        raise ValueError("Exact recording description required")
    physical = config.get("physical_completion", {})
    if "junction_context.json" not in physical.get("context_sources", []) or physical.get("body_key") != "ego_vertices_m":
        raise ValueError("Sourced pinned physical completion descriptor required")
    site = config.get("site")
    if not isinstance(site, dict):
        raise ValueError("Reviewed Native median site required")
    if not site.get("native_map_name") or type(site.get("crossing_id")) is not int:
        raise ValueError("Native map and junction identity required")
    if site.get("ego_highway_id") == site.get("other_highway_id") or any(
            site.get(k) is None for k in ("ego_highway_id", "other_highway_id")):
        raise ValueError("Distinct sourced highway identities required")
    for key in ("polygon_source", "entrance_source", "median_spacing_source",
                "device_review_source", "statutory_crossing_review_source"):
        if not isinstance(site.get(key), str) or not site[key].strip():
            raise ValueError("Missing reviewed site source: " + key)
    if site.get("same_statutory_crossing_reviewed") is not True:
        raise ValueError("Same statutory crossing review required before capture")
    polygon = site.get("crossing_polygon_xy_m")
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError("Crossing polygon required")
    for point in polygon:
        _numbers(point, 2, "crossing vertex")
    for key in POSES:
        _numbers(site.get(key), 4, key + " pose")
    cameras = site.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("All four named camera poses required")
    for name, pose in cameras.items():
        _numbers(pose, 6, name + " camera pose")
    for key in ("ego_release_frame", "other_release_frame"):
        if type(config.get(key)) is not int or not 0 <= config[key] < 1100:
            raise ValueError("Valid " + key + " required")
    for key in ("ego_target_speed_mps", "other_target_speed_mps"):
        value = config.get(key)
        if type(value) not in (int, float) or not 0 < value <= 20 or not math.isfinite(value):
            raise ValueError("Finite positive " + key + " required")
    verify_site_packet(config, base_dir)
    return config


def _transform(carla, pose):
    x, y, z, yaw = pose[:4]
    pitch = pose[4] if len(pose) > 4 else 0
    roll = pose[5] if len(pose) > 5 else 0
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(yaw=yaw, pitch=pitch, roll=roll))


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
def _spawn_ego(world, blueprint, transform):
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise ValueError("Ego Native spawn failed")
    try:
        yield actor
    finally:
        actor.destroy()


def _drive(carla, actor, target_speed, held):
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
    if not math.isfinite(speed):
        raise ValueError("Nonfinite Native speed feedback")
    control = carla.VehicleControl()
    control.throttle = 0.0 if held else max(0.0, min(0.65, 0.18 + 0.16 * (target_speed - speed)))
    control.brake = 1.0 if held else (min(0.4, 0.3 * (speed - target_speed)) if speed > target_speed else 0.0)
    actor.apply_control(control)


def capture(args, config):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot as save_world

    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Use runtime.py capture to materialize exact construction first")
    site = config["site"]
    site_review = verify_site_packet(config, Path(args.config).parent)
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = save_world(client)
    world = client.get_world()
    encoders, frames, errors = {}, 0, []
    capture_helper = None
    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        world_map = world.get_map()
        if world_map.name != site["native_map_name"]:
            raise ValueError("Native map differs from reviewed site")
        transforms = {name: _transform(carla, site[name]) for name in POSES}
        blueprint = world.get_blueprint_library().filter("vehicle.*")[0]
        with _spawn_ego(world, blueprint, transforms["ego_approach"]) as ego:
            with construct_crossing_candidate(
                    world, transforms["ego_approach"], transforms["ego_entry"],
                    transforms["other_approach"], transforms["other_entry"],
                    blueprint, site["crossing_polygon_xy_m"], site["crossing_id"],
                    site["polygon_source"], site["entrance_source"]) as (plan, other):
                context = {
                    "native_map_id": world_map.name, "intersection_id": site["crossing_id"],
                    "ego_highway_id": site["ego_highway_id"],
                    "other_highway_id": site["other_highway_id"],
                    "ego_road_id": plan["approaches"]["ego"]["road_id"],
                    "other_road_id": plan["approaches"]["other"]["road_id"],
                    "crossing_geometry_source": site["polygon_source"],
                    "all_entrances_source": site["entrance_source"],
                    "official_device_inventory_source": site["device_review_source"],
                    "median_spacing_source": site["median_spacing_source"],
                    "same_statutory_crossing": True,
                    "official_device_controls_crossing": False,
                    "opposite_approach_with_left_turn": False,
                    "intersection_polygon_xy_m": site["crossing_polygon_xy_m"],
                    "native_candidate": plan,
                    "statutory_crossing_review_source": site["statutory_crossing_review_source"],
                    "site_review_packet": site_review,
                    "median_spacing_measurement": site_review["median_spacing_measurement"],
                }
                (output / "junction_context.json").write_text(json.dumps(context, indent=2) + "\n")
                camera_transforms = {name: _transform(carla, site["cameras"][name]) for name in CAMERAS}
                with source_cameras(world, ego, camera_transforms) as sensors:
                    queues = {name: Queue() for name in CAMERAS}
                    for name, sensor in sensors.items():
                        sensor.listen(lambda image, name=name: queues[name].put(image))
                    with ExitStack() as stack:
                        for name, (width, height) in SIZES.items():
                            encoders[name] = stack.enter_context(FFV1Writer(output / (name + ".mkv"), width, height))
                        frame_map = stack.enter_context(FrameMap(output / "video_frames.jsonl"))
                        history = stack.enter_context((output / "crossing_history.jsonl").open("x", buffering=1))
                        capture_helper = PipelineCapture(client, ego, output,
                                                         config["selected_case_id"],
                                                         required_observations=config["required_atoms"])
                        try:
                            for i in range(1100):
                                _drive(carla, ego, config["ego_target_speed_mps"], i < config["ego_release_frame"])
                                _drive(carla, other, config["other_target_speed_mps"], i < config["other_release_frame"])
                                world.tick()
                                snapshot = world.get_snapshot()
                                for name in CAMERAS:
                                    image = _sensor_frame(queues[name], snapshot.frame)
                                    encoders[name].write(bytes(image.raw_data))
                                capture_helper.capture(snapshot.frame, snapshot.timestamp.elapsed_seconds)
                                record_crossing_sample(frame_map, history, snapshot, world_map,
                                                       ego, other, plan)
                                frames += 1
                        finally:
                            capture_helper.close()
                            capture_helper = None
    except BaseException as error:
        errors.append(str(error))
        raise
    finally:
        if capture_helper is not None:
            capture_helper.close(confirmed=False)
        restoration = restore(client, saved)
        if not errors:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: encoders[name].exit_code for name in CAMERAS},
                         context={"median_statutory_review_source": site["statutory_crossing_review_source"],
                                  "physical_acceptance_claimed": False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = validate_config(json.loads(Path(args.config).read_text()), Path(args.config).parent)
    if args.check:
        print(json.dumps({"case_id": config["selected_case_id"], "planned_frames": 1100,
                          "named_source_cameras": list(CAMERAS),
                          "cpu_check_passed": True, "carla_started": False,
                          "physical_acceptance_claimed": False}))
        return
    if not args.output_dir:
        raise ValueError("--output-dir required for Native capture")
    capture(args, config)


if __name__ == "__main__":
    main()
