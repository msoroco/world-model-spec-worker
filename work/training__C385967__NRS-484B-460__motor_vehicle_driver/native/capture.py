"""Prospective original Native angle-parking acquisition for exact C385967 cases."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import traceback
import xml.etree.ElementTree as ET

from cameras import check as check_cameras, transform as camera_transform


HERE = Path(__file__).resolve().parent
ASSIGNMENT = "training__C385967__NRS-484B-460__motor_vehicle_driver"
CASES = {ASSIGNMENT + "__selected_03f318de__condition_a": 45,
         ASSIGNMENT + "__selected_03f318de__condition_b": 70}


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def write_new(path, obj):
    with Path(path).open("x") as stream:
        json.dump(obj, stream, indent=2, allow_nan=False)
        stream.write("\n")


def check(config):
    case = config.get("case_id")
    if case not in CASES or config.get("selected_case_id") != case:
        raise ValueError("Exact selected case differs")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != \
            ("NRS-484B-460", "C385967", "motor_vehicle_driver"):
        raise ValueError("Frozen law, cell or actor differs")
    if (config.get("layout"), config.get("maneuver"), config.get("control")) != \
            ("one_way_road", "angle_park", "angle_parking_designation"):
        raise ValueError("Frozen scene differs")
    if (config.get("duration_s"), config.get("rate_hz"),
            config.get("duration_frames")) != (30, 20, 600):
        raise ValueError("Exact 30-second source window differs")
    if config.get("parked_heading_request_deg") != CASES[case] or \
            config.get("device_indicated_angle_deg") != 45 or \
            config.get("curb_heading_deg") != 0 or \
            config.get("space_id") != "angle_space_1":
        raise ValueError("Requested heading, device, curb or space differs")
    if config.get("required_atoms") != ["kin.heading", "kin.speed"]:
        raise ValueError("Pinned native telemetry atom set differs")
    check_cameras(config.get("cameras", []))
    if config.get("parking_brake_mode") not in ("hand_brake", "service_and_hand_brake"):
        raise ValueError("Parking control candidate differs")
    road = ET.fromstring((HERE / "angle-bay-road.xodr").read_text())
    one = road.find("./road")
    if one is None or one.find("./planView/geometry/line") is None:
        raise ValueError("Connected one-way road source absent")
    lanes = {(v.get("id"), v.get("type")) for v in one.findall("./lanes/laneSection/right/lane")}
    if {("-1", "driving"), ("-2", "parking"), ("-3", "sidewalk")} - lanes or \
            one.findall("./lanes/laneSection/left/lane"):
        raise ValueError("One-way driving, parking or curb lane source absent")
    signal = one.find("./signals/signal[@id='902']")
    space = one.find("./objects/object[@id='901']")
    if signal is None or signal.get("name") != "ANGLE PARKING" or \
            signal.get("value") != "45" or space is None or \
            space.get("type") != "parkingSpace":
        raise ValueError("Authored official angle device or highway space absent")
    return {"case_id": case, "frames": 600, "source_cameras": 4,
            "native_executed": False, "actual_device_pixels_review_required": True,
            "physical_completion_claimed": False}


def speed(actor):
    vector = actor.get_velocity()
    value = math.sqrt(vector.x**2 + vector.y**2 + vector.z**2)
    if not math.isfinite(value):
        raise ValueError("Nonfinite Native vehicle velocity")
    return value


def capture(config, output_dir, host, port):
    # Imported only after local CARLA Python has been supplied by execute-delivery.
    import carla
    import numpy as np
    from pipeline_capture import PipelineCapture
    from worker_exchange.world_restore import snapshot, restore

    check(config)
    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output / "config.json").is_file():
        raise ValueError("Use a fresh exact-case materialized output")
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    saved = snapshot(client)
    prior = client.get_world()
    if prior.get_settings().synchronous_mode or [actor for actor in prior.get_actors()
            if actor.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))]:
        raise RuntimeError("Exclusive idle asynchronous world ownership required")
    actors, encoders, logs, image_queues = [], {}, {}, {}
    pipeline = None
    changed = False
    error = None
    restored = None
    count = 0
    try:
        road_text = (HERE / "angle-bay-road.xodr").read_text()
        world = client.generate_opendrive_world(road_text,
            carla.OpendriveGenerationParameters(vertex_distance=.25,
                max_road_length=50, wall_height=0, additional_width=0,
                smooth_junctions=False, enable_mesh_visibility=True,
                enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        world.set_weather(carla.WeatherParameters.ClearNoon)
        native_map = world.get_map()
        driving = native_map.get_waypoint(carla.Location(x=1.75, y=0, z=1),
            project_to_road=False, lane_type=carla.LaneType.Driving)
        parking = native_map.get_waypoint(carla.Location(x=6.5, y=0, z=1),
            project_to_road=False, lane_type=carla.LaneType.Parking)
        if driving is None or parking is None or driving.road_id != parking.road_id or \
                driving.lane_id == parking.lane_id:
            raise RuntimeError("Original driving/parking road identity survey failed")
        native_opendrive = native_map.to_opendrive()
        if "ANGLE PARKING" not in native_opendrive:
            raise RuntimeError("Native map did not retain authored angle device")
        shared = {"provenance": "original_native_capture", "native_road_id": driving.road_id}
        write_new(output / "official_device.json", {**shared,
            "device_id": "902", "device_kind": "official_angle_parking_control",
            "governs_space_id": config["space_id"],
            "indicated_angle_to_curb_deg": config["device_indicated_angle_deg"],
            "authored_road_sha256": sha_bytes(road_text.encode()),
            "native_map_sha256": sha_bytes(native_opendrive.encode()),
            "official_device_review_required": True,
            "actual_sign_pixels_and_authority_unverified": True})
        write_new(output / "road_geometry.json", {**shared,
            "native_map_sha256": sha_bytes(native_opendrive.encode()),
            "driving_lane_id": driving.lane_id, "parking_lane_id": parking.lane_id,
            "space_id": config["space_id"], "curb_tangent_heading_deg": 0,
            "curb_side": "right", "authored_space_center_xy_m": [6.5, 0],
            "actual_curb_and_space_pixels_review_required": True})
        blueprint = world.get_blueprint_library().find("vehicle.lincoln.mkz_2020")
        blueprint.set_attribute("role_name", "c385967_nrs460_ego")
        ego = world.spawn_actor(blueprint, carla.Transform(
            carla.Location(x=6.5, y=0, z=.5),
            carla.Rotation(yaw=config["parked_heading_request_deg"])))
        actors.append(ego)
        brake = 0 if config["parking_brake_mode"] == "hand_brake" else 1
        for _ in range(20):
            ego.apply_control(carla.VehicleControl(brake=brake, hand_brake=True))
            world.tick()
        write_new(output / "parking_context.json", {**shared,
            "case_id": config["case_id"], "space_id": config["space_id"],
            "activity": config["observed_activity_request"],
            "native_actor_id": ego.id, "native_blueprint": ego.type_id,
            "original_body_and_activity_review_required": True,
            "legal_angle_tolerance_defined": False})
        for item in config["cameras"]:
            bp = world.get_blueprint_library().find("sensor.camera.rgb")
            for name, value in (("image_size_x", item["width"]),
                                ("image_size_y", item["height"]),
                                ("fov", item["fov_deg"]), ("sensor_tick", 0)):
                bp.set_attribute(name, str(value))
            sensor = world.spawn_actor(bp, camera_transform(carla, item),
                attach_to=ego if item["pose_strategy"] == "ego_follow" else None)
            actors.append(sensor)
            image_queues[item["name"]] = queue.Queue()
            sensor.listen(image_queues[item["name"]].put)
            logs[item["name"]] = (output / (item["name"] + ".encoder.log")).open("x")
            encoders[item["name"]] = subprocess.Popen(["ffmpeg", "-nostdin",
                "-hide_banner", "-loglevel", "error", "-n", "-f", "rawvideo",
                "-pix_fmt", "rgb24", "-s", f'{item["width"]}x{item["height"]}',
                "-r", "20", "-i", "pipe:0", "-an", "-c:v", "ffv1",
                str(output / (item["name"] + ".mkv"))],
                stdin=subprocess.PIPE, stderr=logs[item["name"]])
        pipeline = PipelineCapture(client, ego, output, config["case_id"],
            visibility=False, required_observations=config["required_atoms"])
        start = world.get_snapshot().timestamp.elapsed_seconds
        with (output / "native_samples.jsonl").open("x") as samples, \
             (output / "body_history.jsonl").open("x") as bodies, \
             (output / "video_frames.jsonl").open("x") as joins:
            for index in range(600):
                control = carla.VehicleControl(brake=brake, hand_brake=True)
                ego.apply_control(control)
                native_frame = world.tick()
                elapsed = world.get_snapshot().timestamp.elapsed_seconds - start
                pose = ego.get_transform()
                lane = native_map.get_waypoint(pose.location,
                    project_to_road=False, lane_type=carla.LaneType.Parking)
                row = {"case_id": config["case_id"],
                    "provenance": "original_native_capture", "sample_index": index,
                    "native_frame": native_frame, "time_s": elapsed,
                    "native_road_id": None if lane is None else lane.road_id,
                    "native_lane_id": None if lane is None else lane.lane_id,
                    "space_id": config["space_id"],
                    "ego_heading_deg": pose.rotation.yaw,
                    "ego_speed_mps": speed(ego),
                    "activity": config["observed_activity_request"],
                    "control": {"brake": control.brake, "hand_brake": control.hand_brake}}
                samples.write(json.dumps(row, allow_nan=False) + "\n")
                pipeline.capture(native_frame, elapsed, extra={"nrs460_native": row})
                vertices = ego.bounding_box.get_world_vertices(pose)
                bodies.write(json.dumps({"case_id": config["case_id"],
                    "provenance": "original_native_capture", "native_frame": native_frame,
                    "time_s": elapsed,
                    "body_vertices_m": [[v.x, v.y, v.z] for v in vertices]},
                    allow_nan=False) + "\n")
                for item in config["cameras"]:
                    image = image_queues[item["name"]].get(timeout=30)
                    while image.frame < native_frame:
                        image = image_queues[item["name"]].get(timeout=30)
                    if image.frame != native_frame:
                        raise RuntimeError("Original camera/Native frame join failed")
                    rgb = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(
                        item["height"], item["width"], 4)[:, :, :3][:, :, ::-1]
                    encoders[item["name"]].stdin.write(rgb.tobytes())
                joins.write(json.dumps({"case_id": config["case_id"],
                    "provenance": "original_native_capture", "video_frame": index,
                    "native_frame": native_frame, "carla_frame": native_frame,
                    "time_s": elapsed}) + "\n")
                count += 1
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
                    raise RuntimeError("Encoder failed: " + name)
            except BaseException as exc:
                error = error or {"encoder_error": str(exc)}
            logs[name].close()
        for actor in reversed(actors):
            try:
                if actor.type_id.startswith("sensor.") and actor.is_listening:
                    actor.stop()
                actor.destroy()
            except BaseException as exc:
                error = error or {"actor_cleanup_error": str(exc)}
        if changed:
            try:
                restored = restore(client, saved)
            except BaseException as exc:
                error = error or {"world_restore_error": str(exc)}
        write_new(output / "native-capture-report.json", {"case_id": config["case_id"],
            "frames": count, "expected_frames": 600, "restoration": restored,
            "error": error, "accepted": False,
            "required_saved_checks": ["official device and governed-space readback",
                "actual curb/edge pixels", "ego body and at-rest action",
                "four-view video and source-frame joins"]})
    if error:
        raise RuntimeError("Native angle parking capture failed; inspect native-capture-report.json")
    return {"case_id": config["case_id"], "frames": count,
            "original_native_captured": True, "physical_acceptance_claimed": False}
