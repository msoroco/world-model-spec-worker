"""Original CARLA acquisition for the C111250 crossing and lane-travel pair.

This module is lazy with respect to CARLA. Its CPU check proves only authored
geometry, route and capture configuration. Original map, body and pixels must
be reviewed after a local recording.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback

from facility import check as check_facility, open_drive
from route_v2 import check as check_routes, route_x


CAMERAS = (("overview", 1920, 1080, 92, (0, -24, 16), "world"),
           ("approach", 1280, 720, 86, (3, -15, 5), "world"),
           ("reference_corner", 1280, 720, 78, (7, -7, 5), "world"),
           ("driver_reference", 1280, 720, 88, (0, 0, 1.7), "ego"))


def check(config):
    case = config.get("case_suffix")
    if case not in ("outside_cycle_lane", "within_cycle_lane"):
        raise ValueError("Unknown exact cycle-facility case")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 30:
        raise ValueError("Capture rate or duration differs")
    if config.get("candidate_id") != "primary":
        raise ValueError("Unprepared candidate")
    if not check_facility()["centerline_preserved"] or not check_routes()["passed"]:
        raise ValueError("Authored construction differs")
    return {"passed": True, "case_id": config["case_id"], "case_suffix": case,
            "candidate_id": "primary", "camera_names": [c[0] for c in CAMERAS],
            "camera_sizes": [[c[1], c[2]] for c in CAMERAS],
            "frames": 600, "native_imported": False,
            "physical_or_legal_success_claimed": False}


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def footprint(actor):
    pose = actor.get_transform()
    points = {(round(v.x, 5), round(v.y, 5)) for v in
              actor.bounding_box.get_world_vertices(pose)}
    if len(points) < 4:
        raise RuntimeError("Native body readback has fewer than four corners")
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return [[min(xs), min(ys)], [max(xs), min(ys)],
            [max(xs), max(ys)], [min(xs), max(ys)]]


def transform(carla, camera):
    _, _, _, _, xyz, attachment = camera
    if attachment == "ego":
        return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]))
    yaw = math.degrees(math.atan2(-xyz[1], -xyz[0]))
    pitch = math.degrees(math.atan2(-xyz[2], math.hypot(xyz[0], xyz[1])))
    return carla.Transform(carla.Location(x=xyz[0], y=xyz[1], z=xyz[2]),
                           carla.Rotation(yaw=yaw, pitch=pitch))


def survey(carla, mapping):
    rows = []
    for y in (-15.0, 0.0, 15.0):
        for x, kind in ((1.75, carla.LaneType.Driving),
                        (4.45, carla.LaneType.Biking)):
            waypoint = mapping.get_waypoint(carla.Location(x=x, y=y, z=2),
                                            project_to_road=False, lane_type=kind)
            if waypoint is None or waypoint.lane_id != (-1 if x < 3 else -2):
                raise RuntimeError("Native motor/bicycle lane readback differs")
            rows.append({"x_m": x, "y_m": y, "road_id": waypoint.road_id,
                         "lane_id": waypoint.lane_id,
                         "lane_type": str(waypoint.lane_type)})
    return rows


def execute(config, output_dir, host, port):
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output / "config.json").is_file():
        raise ValueError("Use a fresh exact-case materialized output directory")
    client = carla.Client(host, int(port)); client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved["settings"].synchronous_mode or [a for a in old.get_actors()
            if a.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))]:
        raise RuntimeError("Requires an exclusive idle asynchronous world")
    owned, encoders, encoder_logs, frame_queues = [], {}, {}, {}
    capture = None; changed = False; frame_count = 0; error = None; restored = None
    try:
        world = client.generate_opendrive_world(open_drive(),
            carla.OpendriveGenerationParameters(vertex_distance=.25,
                max_road_length=50, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings(); settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05; settings.substepping = True
        settings.max_substep_delta_time = .01; settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        mapping = world.get_map(); original_map = mapping.to_opendrive()
        native_survey = survey(carla, mapping)
        write_new(output / "facility-context.json", {
            "source_kind": "original_native_capture",
            "native_map_sha256": hashlib.sha256(original_map.encode()).hexdigest(),
            "authored_map_sha256": hashlib.sha256(open_drive().encode()).hexdigest(),
            "facility_x_m": [3.5, 5.5], "intersection_y_m": [-7.0, 7.0],
            "native_lane_survey": native_survey,
            "native_facility_readback": native_survey,
            "official_designation_proven": False,
            "subsection_3_exception_resolved": False})
        bp = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        bp.set_attribute("role_name", "c111250_ego")
        ego = world.spawn_actor(bp, carla.Transform(
            carla.Location(x=1.75, y=-70, z=.5), carla.Rotation(yaw=90)))
        owned.append(ego)
        obstacle_bp = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        obstacle_bp.set_attribute("role_name", "c111250_conflict_vehicle")
        obstacle = world.spawn_actor(obstacle_bp, carla.Transform(
            carla.Location(x=1.75, y=-3.0, z=.5), carla.Rotation(yaw=90)))
        owned.append(obstacle)
        for _ in range(20):
            ego.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
            obstacle.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
            world.tick()
        write_new(output / "subsection3-context.json", {
            "source_kind": "original_native_capture",
            "exception_clause_requested": "NRS 484B.270(3)(c), to avoid conflict with other traffic",
            "conflict_actor_id": obstacle.id,
            "subsection3_conflict_context": {"actor_id": obstacle.id,
                                                "body_xy_m": footprint(obstacle)},
            "conflict_actor_blueprint": obstacle.type_id,
            "conflict_actor_body_xy_m": footprint(obstacle),
            "conflict_actor_pose_xy_m": [obstacle.get_transform().location.x,
                                         obstacle.get_transform().location.y],
            "same_conflict_actor_policy_in_both_cases": True,
            "exception_legally_resolved": False,
            "yield_to_facility_users_observed": False,
            "physical_or_legal_success_claimed": False})
        for spec in CAMERAS:
            name, width, height, fov, _, attachment = spec
            sensor_bp = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", width), ("image_size_y", height),
                               ("fov", fov), ("sensor_tick", 0)):
                sensor_bp.set_attribute(key, str(value))
            sensor = world.spawn_actor(sensor_bp, transform(carla, spec),
                attach_to=ego if attachment == "ego" else None)
            owned.append(sensor); frame_queues[name] = queue.Queue()
            sensor.listen(frame_queues[name].put)
            encoder_logs[name] = (output / (name + ".encoder.log")).open("x")
            encoders[name] = subprocess.Popen(["ffmpeg", "-nostdin", "-hide_banner",
                "-loglevel", "error", "-n", "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", f"{width}x{height}", "-r", "20", "-i", "pipe:0",
                "-an", "-c:v", "ffv1", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=encoder_logs[name])
        capture = PipelineCapture(client, ego, output, config["case_id"],
            visibility=False, required_observations=config.get("required_atoms", []))
        start = world.get_snapshot().timestamp.elapsed_seconds
        with FrameMap(output / "video_frames.jsonl") as frame_map, \
             (output / "body-history.jsonl").open("x") as bodies, \
             (output / "trace.jsonl").open("x") as trace:
            for index in range(600):
                previous_pose = ego.get_transform()
                previous_speed = ego.get_velocity()
                speed = math.sqrt(previous_speed.x ** 2 + previous_speed.y ** 2 + previous_speed.z ** 2)
                desired_x = route_x(config["case_suffix"], previous_pose.location.y)
                # Proportional lateral controller is an engineering request; saved
                # Native body corners determine actual intersection occupancy.
                steer = max(-.45, min(.45, .18 * (desired_x - previous_pose.location.x)
                    - .012 * (previous_pose.rotation.yaw - 90)))
                ego.apply_control(carla.VehicleControl(
                    throttle=.32 if speed < 3.8 else 0,
                    brake=.18 if speed > 4.3 else 0, steer=steer))
                obstacle.apply_control(carla.VehicleControl(brake=1, hand_brake=True))
                frame = world.tick()
                time_s = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = ego.get_transform(); velocity = ego.get_velocity()
                observed_speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                corners = footprint(ego)
                body_row = {"native_frame": frame, "time_s": time_s,
                            "body_xy_m": corners, "speed_mps": observed_speed,
                            "source_kind": "original_native_capture"}
                bodies.write(json.dumps(body_row, allow_nan=False) + "\n")
                trace.write(json.dumps({"frame": frame, "time_s": time_s,
                    "position_m": [pose.location.x, pose.location.y, pose.location.z],
                    "heading_deg": pose.rotation.yaw, "speed_mps": observed_speed,
                    "velocity_mps": [velocity.x, velocity.y, velocity.z],
                    "body_vertices_m": [[v.x, v.y, v.z] for v in
                         ego.bounding_box.get_world_vertices(pose)]}, allow_nan=False) + "\n")
                capture.capture(frame, time_s, extra={"c111250_native_body": body_row})
                for name, width, height, _, _, _ in CAMERAS:
                    image = frame_queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = frame_queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError("Camera and Native frame identity differ")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        height, width, 4)[:, :, :3][:, :, ::-1]
                    encoders[name].stdin.write(rgb.tobytes())
                frame_map.append(frame, time_s)
                frame_count += 1
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback": traceback.format_exc()}
    finally:
        if capture is not None:
            try: capture.close(confirmed=error is None)
            except BaseException as exc: error = error or {"capture_close_error": str(exc)}
        for name, encoder in encoders.items():
            try:
                encoder.stdin.close()
                if encoder.wait(timeout=180) != 0:
                    raise RuntimeError("Video encoder failed: " + name)
            except BaseException as exc:
                error = error or {"encoder_error": str(exc)}
            encoder_logs[name].close()
        for actor in reversed(owned):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening: actor.stop()
                actor.destroy()
            except BaseException as exc: error = error or {"actor_cleanup_error": str(exc)}
        if changed:
            try: restored = restore(client, saved)
            except BaseException as exc: error = error or {"world_restore_error": str(exc)}
        write_new(output / "native-capture-report.json", {
            "case_id": config["case_id"], "frames": frame_count,
            "expected_frames": 600, "restoration": restored,
            "error": error, "accepted": False})
    if error or frame_count != 600:
        raise RuntimeError("Native capture incomplete; inspect native-capture-report.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    config = json.loads((Path(__file__).parent / "config.json").read_text())
    if args.check:
        print(json.dumps(check(config), sort_keys=True))
    else:
        if not args.output_dir or not args.host or not args.port:
            parser.error("Supply output directory, host and port")
        execute(config, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
