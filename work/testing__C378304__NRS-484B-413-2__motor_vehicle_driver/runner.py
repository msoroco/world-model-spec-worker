"""Exact C378304 Native source capture. CPU check never starts CARLA."""

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path
from queue import Empty, Queue

from native_right_turn_control import RightTurnPolicy, source_row
from right_turn_course import measure_right_turn
from zone_construction import (APPROACH_M, APPROACH_ROAD, CONNECTOR_ROAD,
                               DEPARTURE_ROAD, build_xodr, validate_xodr)

FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER.parents[1] / "runtime/scenario_pipeline"))
CONFIG = json.loads((FOLDER / "config.json").read_text())
CAMERAS = {row["name"]: row for row in CONFIG["cameras"]}
NAMES = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_construction(config=CONFIG):
    cameras = config.get("cameras", [])
    if (config.get("cell_id") != "C378304" or config.get("law_id") != "NRS-484B-413-2"
            or config.get("rate_hz") != 20 or config.get("duration_s") != 45
            or [row.get("name") for row in cameras] != list(NAMES)
            or any((row.get("width"), row.get("height")) !=
                   ((1920, 1080) if row["name"] == "overview" else (1280, 720))
                   for row in cameras)
            or config.get("required_atoms") != ["sig.turn_indicator"]):
        raise ValueError("Wrong exact C378304 Native construction")
    path = FOLDER / config["map_path"]
    if sha(path) != config["map_sha256"] or path.read_text() != build_xodr():
        raise ValueError("Authored map hash/content differs")
    validate_xodr(path.read_text())
    RightTurnPolicy(config["selected_case_id"])
    return {"case_id": config["selected_case_id"], "map_sha256": sha(path),
            "cpu_check_passed": True, "simulation_started": False}


def retain_site_packet(packet_path, output, native_map_name, case_id):
    """Bind an independently reviewed exact-map source; never infer district from XODR."""
    if not packet_path:
        raise ValueError("C378304 requires SCENARIO_C378304_SITE_PACKET before capture")
    packet_path = Path(packet_path).resolve()
    packet = json.loads(packet_path.read_text())
    expected_district = "other" if case_id.endswith("__other_area_right_at_300ft") else "business"
    if (packet.get("authored_map_sha256") != CONFIG["map_sha256"]
            or packet.get("native_map_name") != native_map_name
            or packet.get("case_id") != case_id
            or packet.get("district_type") != expected_district
            or packet.get("independent_review") is not True
            or packet.get("freight_loading_zone_review") is not True):
        raise ValueError("Site packet lacks exact-map independent district/zone review")
    document = Path(packet.get("source_document", "")).resolve()
    if not document.is_file() or sha(document) != packet.get("source_document_sha256"):
        raise ValueError("Freight-zone site document hash differs")
    destination = Path(output) / "freight-zone-site-source.txt"
    if destination.exists():
        raise ValueError("Fresh freight-zone source path required")
    shutil.copyfile(document, destination)
    (Path(output) / "freight-zone-site-packet.json").write_bytes(packet_path.read_bytes())
    return {"district_type": packet["district_type"],
            "district_source": "freight-zone-site-packet.json",
            "freight_loading_zone_source": destination.name,
            "freight_loading_zone_source_sha256": sha(destination),
            "district_review_verified": True}


def select_route(native_map):
    def points(road, length, step):
        stations = [min(i * step, length) for i in range(math.ceil(length / step) + 1)]
        return [native_map.get_waypoint_xodr(road, -1, s) for s in stations]
    approach = points(APPROACH_ROAD, APPROACH_M, 2)
    connector = points(CONNECTOR_ROAD, 5 * math.pi / 2, 0.5)
    departure = points(DEPARTURE_ROAD, 45, 2)
    if any(w is None for w in approach + connector + departure):
        raise ValueError("Native exact right-turn lane station missing")
    if any((w.road_id, w.lane_id) != (APPROACH_ROAD, -1) for w in approach):
        raise ValueError("Native approach identity differs")
    if any((w.road_id, w.lane_id) != (DEPARTURE_ROAD, -1) for w in departure):
        raise ValueError("Native departure identity differs")
    return approach + connector + departure


def control(ego, route, speed_target):
    pose = ego.get_transform()
    xy = (pose.location.x, pose.location.y)
    positions = [(w.transform.location.x, w.transform.location.y) for w in route]
    nearest = min(range(len(route)), key=lambda i: math.dist(xy, positions[i]))
    target = min(nearest + 3, len(route) - 1)
    tx, ty = positions[target]
    bearing = math.degrees(math.atan2(ty - xy[1], tx - xy[0]))
    error = (bearing - pose.rotation.yaw + 180) % 360 - 180
    velocity = ego.get_velocity()
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    throttle = max(0.0, min(0.45, 0.18 * (speed_target - speed)))
    brake = max(0.0, min(1.0, 0.35 * (speed - speed_target)))
    if nearest >= len(route) - 2:
        throttle, brake = 0.0, 1.0
    progress = min(APPROACH_M, float(route[nearest].s)) if route[nearest].road_id == APPROACH_ROAD else APPROACH_M
    return progress, (throttle, brake, max(-0.75, min(0.75, error / 35)))


@contextmanager
def cameras(world, ego, carla):
    def pose(x, y, z, yaw, pitch):
        return carla.Transform(carla.Location(x=x, y=y, z=z),
                               carla.Rotation(yaw=yaw, pitch=pitch))
    transforms = {"overview": pose(-20, -10, 42, 0, -80),
                  "approach": pose(-85, -14, 8, 0, -15),
                  "reference_corner": pose(11, -9, 12, 150, -30),
                  "driver_reference": pose(1, 0, 1.65, 0, -6)}
    sensors = {}
    try:
        for name in NAMES:
            row = CAMERAS[name]
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", row["width"]), ("image_size_y", row["height"]),
                               ("fov", row["fov_deg"]), ("sensor_tick", 0.05)):
                blueprint.set_attribute(key, str(value))
            kwargs = {"attach_to": ego} if name == "driver_reference" else {}
            sensors[name] = world.spawn_actor(blueprint, transforms[name], **kwargs)
            if sensors[name] is None:
                raise ValueError("Native source camera spawn failed: " + name)
        yield sensors
    finally:
        for sensor in reversed(list(sensors.values())):
            sensor.stop()
            sensor.destroy()


def frame(queue, native_frame):
    for _ in range(8):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError("Native camera frame missing") from error
        if image.frame == native_frame:
            return bytes(image.raw_data)
        if image.frame > native_frame:
            raise ValueError("Native camera skipped frame")
    raise ValueError("Native camera frame join failed")


@contextmanager
def video(path, width, height):
    process = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n",
        "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
        "-framerate", "20", "-i", "pipe:0", "-an", "-c:v", "ffv1", "-level", "3",
        "-pix_fmt", "bgr0", str(path)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    count = 0
    def write(data):
        nonlocal count
        if len(data) != width * height * 4 or process.poll() is not None:
            raise ValueError("Native camera BGRA/encoder mismatch")
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


def capture(args):
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as save_world, restore
    import carla
    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Use runtime.py capture for exact construction")
    check_construction()
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = save_world(client)
    helper = None
    frames = 0
    completed = False
    try:
        world = client.generate_opendrive_world(build_xodr())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        weather = CONFIG.get("weather", {})
        if weather:
            native_weather = world.get_weather()
            for key in ("cloudiness", "precipitation", "wetness"):
                value = weather.get(key)
                if type(value) not in (int, float) or not 0 <= value <= 100:
                    raise ValueError("Invalid exact-case Native weather: " + key)
                setattr(native_weather, key, float(value))
            world.set_weather(native_weather)
        route = select_route(world.get_map())
        blueprints = world.get_blueprint_library().filter("vehicle.*")
        if not blueprints:
            raise ValueError("No Native vehicle blueprint")
        ego = world.try_spawn_actor(blueprints[0], route[0].transform)
        if ego is None:
            raise ValueError("Native ego spawn failed")
        try:
            source = retain_site_packet(os.environ.get("SCENARIO_C378304_SITE_PACKET"),
                                        output, world.get_map().name, CONFIG["selected_case_id"])
            policy = RightTurnPolicy(CONFIG["selected_case_id"])
            with cameras(world, ego, carla) as sensors:
                queues = {name: Queue() for name in NAMES}
                for name, sensor in sensors.items():
                    sensor.listen(lambda image, name=name: queues[name].put(image))
                with ExitStack() as stack:
                    writers = {name: stack.enter_context(video(output / (name + ".mkv"),
                                   CAMERAS[name]["width"], CAMERAS[name]["height"])) for name in NAMES}
                    frame_map = stack.enter_context(FrameMap(output / "video_frames.jsonl"))
                    history = stack.enter_context((output / "drive_history.jsonl").open("x", buffering=1))
                    helper = PipelineCapture(client, ego, output, CONFIG["selected_case_id"],
                                             required_observations=CONFIG["required_atoms"])
                    rows = []
                    try:
                        for _ in range(CONFIG["duration_s"] * CONFIG["rate_hz"]):
                            progress, (throttle, brake, steer) = control(ego, route, CONFIG["requested_speed_mps"])
                            policy.apply(ego, carla.VehicleLightState,
                                         max(progress, policy.last_progress or progress))
                            ego.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
                            world.tick()
                            snap = world.get_snapshot()
                            waypoint = world.get_map().get_waypoint(ego.get_location(), project_to_road=False)
                            if waypoint is None:
                                raise ValueError("Native ego left exact road")
                            row = source_row(snap, ego, waypoint, carla.VehicleLightState)
                            for name in NAMES:
                                writers[name](frame(queues[name], snap.frame))
                            frame_map.append(row["frame"], row["time_s"])
                            helper.capture(row["frame"], row["time_s"])
                            history.write(json.dumps(row, allow_nan=False) + "\n")
                            rows.append(row)
                            frames += 1
                    finally:
                        helper.close()
                        helper = None
            context = dict(source, native_map_id=world.get_map().name,
                           approach_road_id=APPROACH_ROAD, approach_lane_id=-1,
                           outgoing_road_id=DEPARTURE_ROAD, outgoing_lane_id=-1,
                           native_route_source="Native get_waypoint_xodr readback")
            observed_weather = world.get_weather()
            context["native_weather_readback"] = {
                key: float(getattr(observed_weather, key))
                for key in ("cloudiness", "precipitation", "wetness")}
            context["turn_onset_frame"] = measure_right_turn(rows, context)["turn_onset_frame"]
            (output / "route_context.json").write_text(json.dumps(context, indent=2) + "\n")
            completed = True
        finally:
            ego.destroy()
    finally:
        if helper is not None:
            helper.close(confirmed=False)
        restoration = restore(client, saved)
        if completed:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: 0 for name in NAMES},
                         context={"site_packet_bound": True, "physical_acceptance_claimed": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check_construction()))
    elif args.output_dir:
        capture(args)
    else:
        parser.error("--output-dir is required for Native capture")
