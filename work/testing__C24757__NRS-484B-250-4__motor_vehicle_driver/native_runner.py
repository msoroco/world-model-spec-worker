"""Source-bound two-vehicle Native capture for C24757.

Imports CARLA only when capture is explicitly dispatched. CPU plan validation
does not certify a Native site or any physical/legal observation.
"""

import argparse
import hashlib
import json
import math
import subprocess
from contextlib import ExitStack, contextmanager
from pathlib import Path
from queue import Empty, Queue

from native_inoperative_control import StopController, all_heads_off, governing_lights
from native_site_contract import validate_site
from native_stop_sources import signed_front_distance, source_row
from saved_finalizer import CAMERAS, finalize_saved


SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def validate_capture_plan(config, packet_root):
    receipt = validate_site(config, packet_root)
    if config.get("cell_id") != "C24757" or config.get("law_id") != "NRS-484B-250-4":
        raise ValueError("Exact C24757 capture identity required")
    if (not str(config.get("selected_case_id", "")).startswith(
            "testing__C24757__NRS-484B-250-4__motor_vehicle_driver__") or
            not isinstance(config.get("required_atoms"), list)):
        raise ValueError("Selected C24757 case and atom contract required")
    physical = config.get("physical_completion")
    if (not isinstance(physical, dict) or
            physical.get("motion_source") != "vehicle_signal_history.jsonl" or
            physical.get("body_key") != "ego.body_vertices_xy_m" or
            physical.get("context_sources") != ["junction_context.json"]):
        raise ValueError("Source-bound physical completion descriptor required")
    if config.get("rate_hz") != 20 or type(config.get("duration_s")) is not int or not 5 <= config["duration_s"] <= 120:
        raise ValueError("20 Hz bounded Native duration required")
    cameras = config.get("cameras")
    if not isinstance(cameras, list) or [c.get("name") for c in cameras] != list(CAMERAS):
        raise ValueError("Four named source cameras required")
    for row in cameras:
        if (row.get("width"), row.get("height")) != SIZES[row["name"]]:
            raise ValueError("Source camera dimensions differ from pinned profile")
        pose = row.get("pose")
        if (not isinstance(pose, dict) or set(pose) != {"x", "y", "z", "yaw", "pitch"} or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in pose.values()) or
                type(row.get("fov_deg")) not in (int, float) or not 20 <= row["fov_deg"] <= 120):
            raise ValueError("Finite sourced camera pose and FOV required")
    routes = config.get("actor_routes")
    if not isinstance(routes, dict) or set(routes) != {"ego", "other"}:
        raise ValueError("Two Native actor routes required")
    lanes = {tuple(lane) for lane in config["site"]["entrance_road_lanes"]}
    for who, route in routes.items():
        spawn = route.get("spawn")
        if (not isinstance(spawn, list) or len(spawn) != 3 or
                any(type(v) is not int for v in spawn[:2]) or
                type(spawn[2]) not in (int, float) or not math.isfinite(spawn[2]) or
                tuple(spawn[:2]) not in lanes):
            raise ValueError("Sourced governed Native spawn required: " + who)
        targets = route.get("target_xy_m")
        if (not isinstance(targets, list) or len(targets) < 2 or
                any(not isinstance(p, list) or len(p) != 2 or
                    any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in targets)):
            raise ValueError("Finite Native route targets required: " + who)
        if (type(route.get("release_frame")) is not int or route["release_frame"] < 0 or
                type(route.get("target_speed_mps")) not in (int, float) or
                not 0 < route["target_speed_mps"] <= 20):
            raise ValueError("Bounded Native stop/release control required: " + who)
        if route.get("release_rule") not in ("scheduled", "after_other_clear"):
            raise ValueError("Named Native release condition required: " + who)
    if routes["ego"]["spawn"][:2] == routes["other"]["spawn"][:2]:
        raise ValueError("Two distinct Native approaches required")
    if all(route["release_rule"] == "after_other_clear" for route in routes.values()):
        raise ValueError("Circular Native release conditions")
    return receipt


def _steer(actor, targets):
    transform = actor.get_transform()
    loc = transform.location
    nearest = min(range(len(targets)), key=lambda i: math.hypot(targets[i][0]-loc.x, targets[i][1]-loc.y))
    target = targets[min(nearest + 1, len(targets)-1)]
    desired = math.degrees(math.atan2(target[1]-loc.y, target[0]-loc.x))
    error = (desired - transform.rotation.yaw + 180) % 360 - 180
    return max(-1.0, min(1.0, error / 45.0))


def _camera_frame(queue, expected):
    for _ in range(8):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError("Source camera frame missing") from error
        if image.frame == expected:
            return bytes(image.raw_data)
        if image.frame > expected:
            raise ValueError("Source camera skipped Native frame")
    raise ValueError("Source camera frame join failed")


@contextmanager
def _source_cameras(world, ego, carla, plan):
    sensors = {}
    try:
        for row in plan:
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", row["width"]), ("image_size_y", row["height"]),
                               ("fov", row["fov_deg"]), ("sensor_tick", 0.05)):
                blueprint.set_attribute(key, str(value))
            pose = row["pose"]
            transform = carla.Transform(carla.Location(x=pose["x"], y=pose["y"], z=pose["z"]),
                                        carla.Rotation(yaw=pose["yaw"], pitch=pose["pitch"]))
            kwargs = {"attach_to": ego} if row["name"] == "driver_reference" else {}
            sensor = world.spawn_actor(blueprint, transform, **kwargs)
            if sensor is None:
                raise ValueError("Native source camera spawn failed: " + row["name"])
            sensors[row["name"]] = sensor
        yield sensors
    finally:
        for sensor in reversed(list(sensors.values())):
            sensor.stop()
            sensor.destroy()


@contextmanager
def _ffv1(path, size):
    width, height = size
    if Path(path).exists():
        raise ValueError("Fresh source video required")
    process = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n",
        "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
        "-framerate", "20", "-i", "pipe:0", "-an", "-c:v", "ffv1", "-level", "3",
        "-pix_fmt", "bgr0", str(path)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    count = 0
    def write(data):
        nonlocal count
        if len(data) != width*height*4 or process.poll() is not None:
            raise ValueError("Native source-camera BGRA size/encoder mismatch")
        process.stdin.write(data)
        count += 1
    try:
        yield write
    finally:
        process.stdin.close()
        code = process.wait(timeout=60)
        stderr = process.stderr.read().decode(errors="replace")
        process.stderr.close()
        if code or not count:
            raise ValueError("Native FFV1 encoder failed: " + stderr[-500:])


def capture_native(args, config):
    """Capture only after exact runtime materialization and reviewed site binding."""
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore
    from shapely.geometry import MultiPoint, Polygon

    packet_root = Path(__file__).resolve().parent
    validate_capture_plan(config, packet_root)
    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Use runtime.py capture to materialize exact construction")
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = snapshot(client)
    actors = []
    collector = None
    frames = 0
    error = None
    try:
        available = client.get_available_maps()
        map_name = config["site"]["native_map_name"]
        if map_name not in available:
            raise ValueError("Reviewed Native map unavailable")
        world = client.load_world(map_name)
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        if world.get_map().name != map_name:
            raise ValueError("Reviewed Native map readback failed")
        blueprints = world.get_blueprint_library().filter("vehicle.*")
        if not blueprints:
            raise ValueError("No Native vehicle blueprint")
        blueprint = blueprints[0]
        routes = config["actor_routes"]
        for who in ("ego", "other"):
            road, lane, station = routes[who]["spawn"]
            waypoint = world.get_map().get_waypoint_xodr(road, lane, station)
            if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (road, lane):
                raise ValueError("Native approach waypoint differs from reviewed route")
            transform = waypoint.transform
            transform.location.z += 0.5
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError("Native two-actor spawn failed")
            actors.append(actor)
        ego, other = actors
        lights = governing_lights(world, config["site"]["entrance_road_lanes"])
        selected = next((light for light in lights if light.id == config["site"]["native_signal_id"]), None)
        if selected is None:
            raise ValueError("Reviewed Native signal does not govern a selected approach")
        controllers = {who: StopController(routes[who]["release_frame"], routes[who]["target_speed_mps"])
                       for who in routes}
        polygon = Polygon(config["site"]["intersection_polygon_xy_m"])
        entered = {"ego": False, "other": False}
        cleared = {"ego": False, "other": False}
        with all_heads_off(world, lights, carla.TrafficLightState):
            with _source_cameras(world, ego, carla, config["cameras"]) as sensors:
                queues = {name: Queue() for name in CAMERAS}
                for name, sensor in sensors.items():
                    sensor.listen(lambda image, name=name: queues[name].put(image))
                with ExitStack() as stack:
                    writers = {name: stack.enter_context(_ffv1(output/(name+".mkv"), size))
                               for name, size in SIZES.items()}
                    frame_map = stack.enter_context(FrameMap(output/"video_frames.jsonl"))
                    history = stack.enter_context((output/"vehicle_signal_history.jsonl").open("x", buffering=1))
                    collector = PipelineCapture(client, ego, output, config["selected_case_id"],
                                                required_observations=config["required_atoms"])
                    try:
                        for index in range(config["duration_s"]*20):
                            for who, actor in (("ego", ego), ("other", other)):
                                boundary = config["site"]["stop_boundary" if who == "ego" else "other_stop_boundary"]
                                verts = actor.bounding_box.get_world_vertices(actor.get_transform())
                                xy = [[v.x, v.y] for v in verts]
                                signed = signed_front_distance(xy, boundary["point_xy_m"],
                                                               boundary["upstream_normal_xy"])
                                partner = "other" if who == "ego" else "ego"
                                release = (routes[who]["release_rule"] == "scheduled" or cleared[partner])
                                controllers[who].step(carla, actor, index, signed,
                                    steer=_steer(actor, routes[who]["target_xy_m"]),
                                    release_condition=release)
                            world.tick()
                            snap = world.get_snapshot()
                            if any(light.get_state() != carla.TrafficLightState.Off for light in lights):
                                raise ValueError("Native governed signal changed from Off")
                            for name in CAMERAS:
                                writers[name](_camera_frame(queues[name], snap.frame))
                            frame_map.append(snap.frame, snap.timestamp.elapsed_seconds)
                            collector.capture(snap.frame, snap.timestamp.elapsed_seconds)
                            row = source_row(int(snap.frame),
                                float(snap.timestamp.elapsed_seconds), selected, ego, other,
                                config["site"])
                            for who in ("ego", "other"):
                                inside = MultiPoint(row[who]["body_vertices_xy_m"]).convex_hull.intersects(polygon)
                                if inside:
                                    entered[who] = True
                                elif entered[who]:
                                    cleared[who] = True
                            history.write(json.dumps(row, allow_nan=False) + "\n")
                            frames += 1
                    finally:
                        collector.close(confirmed=frames == config["duration_s"]*20)
                        collector = None
        site = config["site"]
        context = {"native_map_id": site["native_map_name"],
                   "intersection_id": site["intersection_id"],
                   "native_signal_id": site["native_signal_id"],
                   "installed_uncovered_vehicular_heads": site["installed_uncovered_vehicular_heads"],
                   "stop_line_exists": site["stop_line_exists"],
                   "crosswalk_exists": site["crosswalk_exists"],
                   "other_stop_boundary": {"kind": site["other_stop_boundary"]["kind"],
                                           "source": site["other_stop_boundary"]["source"]},
                   "intersection_polygon_xy_m": site["intersection_polygon_xy_m"],
                   "signal_head_video_source": site["approach_visibility_source"],
                   "lane_governance_source": config["site_review"]["sha256"],
                   site["stop_boundary"]["kind"] + "_source": site["stop_boundary"]["source"]}
        (output/"junction_context.json").write_text(json.dumps(context, indent=2) + "\n")
    except BaseException as exc:
        error = exc
        raise
    finally:
        if collector is not None:
            collector.close(confirmed=False)
        for actor in reversed(actors):
            actor.destroy()
        restoration = restore(client, saved)
        if error is None:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: 0 for name in CAMERAS},
                         context={"native_site_candidate": True, "legal_review_verified": False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.attempt:
        if not args.output:
            parser.error("--output required with --attempt")
        finalize_saved(args.attempt, args.output)
        return
    config = json.loads((Path(__file__).parent/"config.json").read_text())
    if args.check:
        print(json.dumps(validate_capture_plan(config, Path(__file__).parent)))
    elif args.output_dir:
        capture_native(args, config)
    else:
        parser.error("--check, --output-dir or --attempt required")


if __name__ == "__main__":
    main()
