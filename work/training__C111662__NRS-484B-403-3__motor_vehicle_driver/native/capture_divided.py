"""Unaccepted original CARLA attempt for the divided-highway opening branch."""
import argparse
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from build import RATE
from capture import actor_row, control, sha, xyz
from divided_opening import BRANCH, CASE, check
from frontage import authored_plan, spawn_and_measure

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def camera_specs(policy):
    """Exact current four-source capability profile for a median U-turn."""
    if policy not in ("standard", "elevated_overview"):
        raise ValueError("Unknown camera policy")
    height = 55 if policy == "elevated_overview" else 38
    return (("overview", 1920, 1080, (-20, 0, height), -45, -90),
            ("approach", 1280, 720, (-65, -10, 4), 0, -8),
            ("reference_corner", 1280, 720, (10, 15, 12), -135, -35),
            ("driver_reference", 1280, 720, (18, -10, 9), 145, -24))


def capture(bundle, output, host, port):
    import carla
    import numpy as np
    from scenario_pipeline.worker_exchange.world_restore import snapshot, restore

    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requests = [json.loads(line) for line in
                (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    previous = client.get_world()
    saved_world = snapshot(client)
    if previous.get_settings().synchronous_mode or any(
            actor.type_id.startswith(("vehicle.", "walker.", "sensor."))
            for actor in previous.get_actors()):
        raise RuntimeError("Exclusive idle asynchronous CARLA world required")
    output.mkdir(parents=True, exist_ok=False)
    owned, sensors, encoders, logs = [], {}, {}, {}
    changed = False
    frames = 0
    error = restoration = None
    try:
        world = client.generate_opendrive_world(
            (bundle / "divided-highway.xodr").read_text(),
            carla.OpendriveGenerationParameters(
                vertex_distance=.25, max_road_length=100, wall_height=0,
                additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map()
        lanes = {}
        for name, road_id, lane_id, station, expected in (
            ("reference_eastbound", 503, -2, 40, carla.LaneType.Driving),
            ("reference_westbound", 503, 2, 40, carla.LaneType.Driving),
            ("reference_median", 503, 1, 40, carla.LaneType.Median),
            ("opening_eastbound", 504, -2, 10, carla.LaneType.Driving),
            ("opening_crossing", 504, 1, 10, carla.LaneType.Driving),
            ("opening_westbound", 504, 2, 10, carla.LaneType.Driving),
            ("departure_median", 505, 1, 40, carla.LaneType.Median),
        ):
            wp = mapping.get_waypoint_xodr(road_id, lane_id, station)
            if wp is None or wp.road_id != road_id or wp.lane_id != lane_id or wp.lane_type != expected:
                raise RuntimeError("Generated median or opening lane missing: " + name)
            lanes[name] = {"road_id": road_id, "lane_id": lane_id,
                           "lane_type": str(wp.lane_type),
                           "native_xyz_m": xyz(wp.transform.location)}
        frontage_plan = json.loads((bundle / 'frontage-plan.json').read_text())
        if frontage_plan != authored_plan():
            raise RuntimeError('Source-pinned frontage plan differs')
        frontage_readback = spawn_and_measure(world, carla, frontage_plan, owned)
        (output / 'native-frontage-readback.json').write_text(
            json.dumps(frontage_readback, indent=2) + '\n')
        ego = world.try_spawn_actor(
            world.get_blueprint_library().find(cfg["ego_blueprint"]),
            carla.Transform(carla.Location(x=-80, y=-6, z=1.5),
                            carla.Rotation(yaw=0)))
        if ego is None:
            raise RuntimeError("Physical ego vehicle did not spawn")
        owned.append(ego)
        specs = camera_specs(cfg["camera_policy"])
        for name, width, pixels, position, yaw, pitch in specs:
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", pixels),
                               ("fov", 80), ("sensor_tick", 0)):
                bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(
                bp, carla.Transform(carla.Location(*position),
                                    carla.Rotation(yaw=yaw, pitch=pitch)))
            owned.append(sensor)
            sensors[name] = queue.Queue()
            sensor.listen(sensors[name].put)
            logs[name] = (output / (name + ".encoder.log")).open("x")
            encoders[name] = subprocess.Popen(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{pixels}",
                 "-r", str(RATE), "-i", "pipe:0", "-an", "-c:v", "ffv1",
                 str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=logs[name])
        (output / "native-map-readback.json").write_text(json.dumps({
            "source_kind": "original_native",
            "road_sha256": sha(bundle / "divided-highway.xodr"),
            "native_map_sha256": __import__("hashlib").sha256(
                mapping.to_opendrive().encode()).hexdigest(),
            "lane_readback": lanes, "ego_actor_id": ego.id,
            "authored_divided_highway": True, "district_designation_verified": False,
            "opening_exception_legally_verified": False,
            "legal_verdict": None}, indent=2) + "\n")
        for _ in range(20):
            world.tick()
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / "native-raw-actors.jsonl").open("x") as actor_file, \
                (output / "video_frames.jsonl").open("x") as video_file:
            for i, request in enumerate(requests):
                ego.apply_control(control(ego, requests[min(i + 4, len(requests) - 1)], carla))
                native_frame = world.tick()
                t = world.get_snapshot().timestamp.elapsed_seconds - start
                wp = mapping.get_waypoint(
                    ego.get_location(), project_to_road=False,
                    lane_type=carla.LaneType.Any)
                actor_file.write(json.dumps({
                    "frame": i, "native_frame": native_frame, "time_s": t,
                    "source_kind": "original_native", "request_frame": request["frame"],
                    "ego": actor_row(ego),
                    "ego_road_id": None if wp is None else wp.road_id,
                    "requested_phase": request["requested_phase"],
                    "authored_divided_highway": True,
                    "district_designation_verified": False,
                    "opening_exception_legally_verified": False,
                    "legal_verdict": None}, allow_nan=False) + "\n")
                for name, width, pixels, *_ in specs:
                    image = sensors[name].get(timeout=30)
                    while image.frame < native_frame:
                        image = sensors[name].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError("Camera/native frame join failed")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        pixels, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                video_file.write(json.dumps({
                    "video_frame": i, "native_frame": native_frame, "time_s": t}) + "\n")
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
            "config_sha256": sha(bundle / "config.json"),
            "requested_frames": len(requests), "observed_frames": frames,
            "restoration": restoration, "error": error,
            "accepted": False, "delivery_ready": False,
            "legal_verdict": None}, indent=2) + "\n")
    if error:
        raise RuntimeError("C111662 divided-highway Native attempt failed; inspect report")


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
        args.bundle = Path("work") / CASE.name / "native" / "divided-opening" / "drafts" / suffix / selection["candidate_id"]
    if args.check:
        print(json.dumps(check(args.bundle)))
    else:
        if args.output is None:
            parser.error("--output required for original capture")
        capture(args.bundle, args.output, args.host, args.port)
