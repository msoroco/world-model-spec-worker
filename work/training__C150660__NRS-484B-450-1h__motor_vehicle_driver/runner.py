"""Attempt the fixed one-way safety-zone stop with original Native sources."""

import argparse
import json
import math
import queue
import subprocess
import sys
from pathlib import Path

from case_specs import CASES, target_x
from road import (CURB_Y_M, EGO_LANE_ID, ZONE_END_M, ZONE_NEAR_Y_M,
                  ZONE_START_M, check as road_check, open_drive)

FRAMES = 600
RATE_HZ = 20
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))
ASSIGNMENT = "training__C150660__NRS-484B-450-1h__motor_vehicle_driver"


def check():
    road = road_check()
    if FRAMES / RATE_HZ != 30 or len(CAMERAS) != 4:
        raise ValueError("Exact duration/camera plan changed")
    if not (target_x("end_25") < target_x("end_30") < target_x("end_35")):
        raise ValueError("Curb-end engineering probes changed")
    if not (target_x("start_35") < target_x("start_30") < target_x("start_25")):
        raise ValueError("Start-side curb-end engineering probes changed")
    if not (target_x("start_25") < ZONE_START_M < target_x("selected_6214a61f__condition_a") < ZONE_END_M):
        raise ValueError("Requested approach positions changed")
    return {"passed": True, "road": road, "cases": len(CASES), "frames": FRAMES,
            "rate_hz": RATE_HZ, "cameras": [item[0] for item in CAMERAS],
            "physical_acceptance_claimed": False}


def _camera_pose(carla, name):
    if name == "driver_reference":
        return carla.Transform(carla.Location(x=.7, y=0, z=1.4),
                               carla.Rotation(pitch=-10)), True
    poses = {"overview": (90, -18, 38, -65),
             "approach": (63, -10, 9, -13),
             "reference_corner": (102, -13, 14, -35)}
    x, y, z, pitch = poses[name]
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch)), False


def _context(world, carla, library, kind, target):
    """Spawn visible context requests; their statutory authority needs review."""
    owned = []
    requests = []
    if kind == "traffic_conflict":
        blueprint = library.find("vehicle.audi.a2")
        pose = carla.Transform(carla.Location(x=target + 8, y=-6.4, z=.7),
                               carla.Rotation(yaw=0))
        actor = world.try_spawn_actor(blueprint, pose)
        if actor is None:
            raise RuntimeError("Conflict vehicle did not spawn")
        actor.set_simulate_physics(False)
        owned.append(actor)
        requests.append({"kind": kind, "actor_id": actor.id,
                         "source_status": "native_actor_only"})
    elif kind in ("other_law", "officer_direction", "device_direction"):
        # Scripted requests do not themselves establish applicable law, officer
        # authority or an official device; the original survey must do so.
        blueprint = library.find("static.prop.trafficcone01")
        pose = carla.Transform(carla.Location(x=target + 6, y=-7.0, z=.1))
        actor = world.try_spawn_actor(blueprint, pose)
        if actor is None:
            raise RuntimeError("Context marker did not spawn")
        owned.append(actor)
        requests.append({"kind": kind, "actor_id": actor.id,
                         "source_status": "visual_marker_not_authority"})
    return owned, requests


def execute(case_id, output_dir, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot

    suffix = case_id[len(ASSIGNMENT) + 2:] if case_id.startswith(ASSIGNMENT + "__") else ""
    if suffix not in CASES:
        raise ValueError("Unknown exact safety-zone case")
    config = json.loads((Path(__file__).parent / "config.json").read_text())
    if config.get("selected_case_id") != case_id or config.get("case_id") != case_id:
        raise ValueError("Materialized safety-zone case differs")
    position, activity, exception, gap_ft = CASES[suffix]
    if (config.get("position_request") != position or
            config.get("activity_request") != activity or
            config.get("exception_request") != exception or
            config.get("requested_curb_end_gap_ft") != gap_ft):
        raise ValueError("Safety-zone construction request differs")
    check()
    brake_lead_seconds = float(config.get("brake_lead_seconds", 1.4))
    if not 1 <= brake_lead_seconds <= 2.2:
        raise ValueError("Brake lead outside tested engineering range")
    output = Path(output_dir).resolve()
    if any((output / name).exists() for name in ("zone_raw.json", "video_frames.jsonl", "road.xodr")):
        raise ValueError("Retain prior original source; use a fresh attempt")
    client = carla.Client(host, int(port))
    client.set_timeout(180)
    prior = snapshot(client)
    old_world = client.get_world()
    if prior["settings"].synchronous_mode or any(
            actor.type_id.startswith(("vehicle.", "walker.", "sensor.", "controller."))
            for actor in old_world.get_actors()):
        raise RuntimeError("Requires exclusive idle asynchronous Native world")
    owned, encoders, camera_queues = [], {}, {}
    capture = None
    changed = False
    complete = False
    try:
        world = client.generate_opendrive_world(open_drive(),
            carla.OpendriveGenerationParameters(vertex_distance=1, max_road_length=50,
                wall_height=0, additional_width=0, smooth_junctions=False,
                enable_mesh_visibility=True, enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        native_map = world.get_map()
        lane = native_map.get_waypoint_xodr(1, EGO_LANE_ID, 40)
        if lane is None or lane.lane_type != carla.LaneType.Driving:
            raise RuntimeError("One-way approach driving lane absent")
        output.mkdir(parents=True, exist_ok=True)
        (output / "road.xodr").write_text(native_map.to_opendrive())
        (output / "authored-road.xodr").write_text(open_drive())
        library = world.get_blueprint_library()
        ego_blueprint = library.find("vehicle.tesla.model3")
        ego_blueprint.set_attribute("role_name", "c150660_safety_zone_subject")
        origin_x = min(40.0, target_x(suffix) - 30.0)
        ego_pose = carla.Transform(carla.Location(x=origin_x, y=-1.85, z=.7),
                                   carla.Rotation(yaw=0))
        ego = world.try_spawn_actor(ego_blueprint, ego_pose)
        if ego is None:
            raise RuntimeError("Safety-zone subject did not spawn")
        owned.append(ego)
        target = target_x(suffix, ego.bounding_box.extent.x, .1)
        target_y = CURB_Y_M + ego.bounding_box.extent.y + .1
        context_actors, context_requests = _context(world, carla, library, exception, target)
        owned.extend(context_actors)
        capture = PipelineCapture(client, ego, output, case_id, visibility=False,
                                  required_observations=config.get("required_atoms", []))
        for name, width, height in CAMERAS:
            blueprint = library.find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("sensor_tick", ".05")
            blueprint.set_attribute("fov", "85")
            pose, attached = _camera_pose(carla, name)
            camera = world.spawn_actor(blueprint, pose, attach_to=ego if attached else None)
            owned.append(camera)
            received = queue.Queue()
            camera.listen(received.put)
            camera_queues[name] = received
            encoders[name] = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}",
                "-r", str(RATE_HZ), "-i", "-", "-frames:v", str(FRAMES),
                "-c:v", "ffv1", "-level", "1", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        rows = []
        with FrameMap(output / "video_frames.jsonl") as frame_map, (output / "trace.jsonl").open("x") as trace:
            start = None
            for index in range(FRAMES):
                pose = ego.get_transform()
                speed_before = ego.get_velocity().length()
                remaining = target - pose.location.x
                y_error = target_y - pose.location.y
                steering = max(-.25, min(.25, .09 * y_error)) if pose.location.x < target - 10 else 0
                braking = remaining <= max(2.0, speed_before * brake_lead_seconds)
                ego.apply_control(carla.VehicleControl(
                    throttle=0 if braking else .23, brake=1.0 if braking else 0,
                    hand_brake=activity in ("stand", "park") and braking and speed_before < .4,
                    steer=steering))
                frame = world.tick()
                snap = world.get_snapshot()
                if snap.frame != frame:
                    raise RuntimeError("Native snapshot frame mismatch")
                if start is None:
                    start = snap.timestamp.elapsed_seconds
                elapsed = snap.timestamp.elapsed_seconds - start
                capture.capture(frame, elapsed)
                joined = {}
                for name, received in camera_queues.items():
                    image = received.get(timeout=30)
                    while image.frame < frame:
                        image = received.get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError("Camera Native frame mismatch: " + name)
                    encoders[name].stdin.write(image.raw_data)
                    joined[name] = frame
                frame_map.append(frame, elapsed, camera_native_frames=joined)
                pose = ego.get_transform()
                velocity = ego.get_velocity()
                extent = ego.bounding_box.extent
                corners = []
                for dx in (-extent.x, extent.x):
                    for dy in (-extent.y, extent.y):
                        point = pose.transform(carla.Location(x=dx, y=dy, z=0))
                        corners.append([point.x, point.y])
                speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
                rows.append({"frame": index, "time_s": index / RATE_HZ,
                             "native_frame": frame, "vehicle_stopped": speed < .2,
                             "stop_state_source": "native_velocity_and_vehicle_control",
                             "speed_mps": speed, "vehicle_footprint_corners_m": corners,
                             "vehicle_actor_id": ego.id, "requested_position": position})
                trace.write(json.dumps({"frame": frame, "time_s": elapsed,
                                        "position_m": [pose.location.x, pose.location.y, pose.location.z],
                                        "heading_deg": pose.rotation.yaw, "speed_mps": speed}) + "\n")
        (output / "zone_raw.json").write_text(json.dumps({
            "case_id": case_id, "source_kind": "native_raw_capture",
            "zone": {"x_start_m": ZONE_START_M, "x_end_m": ZONE_END_M,
                     "curb_y_m": CURB_Y_M, "zone_near_y_m": ZONE_NEAR_Y_M,
                     "zone_map_source": "authored-road.xodr plus road.xodr review",
                     "curb_map_source": "road.xodr shoulder edge survey"},
            "construction_request": {"position": position, "activity": activity,
                                     "exception": exception, "gap_ft": gap_ft,
                                     "target_center_x_m": target,
                                     "context_requests": context_requests},
            "frames": rows}, separators=(",", ":")) + "\n")
        for name, process in encoders.items():
            process.stdin.close()
            error = process.stderr.read()
            if process.wait(timeout=180):
                raise RuntimeError("Native camera encoding failed: " + name + ": " + error.decode()[-400:])
        (output / "context-survey.template.json").write_text(json.dumps({
            "case_id": case_id, "review_kind": "original_source_review",
            "safety_zone_official_status": None, "zone_marker_readback": None,
            "adjacent_curb_readback": None, "halt_purpose": None,
            "traffic_conflict": None, "applicable_law_direction": None,
            "officer_direction": None, "device_direction": None,
            "actual_pixels_reviewed": None, "independent_reviewer": None,
            "zone_raw_sha256": None, "road_sha256": None,
            "video_frames_sha256": None,
            "video_sha256": {name + ".mkv": None for name in
                             ("overview", "approach", "reference_corner", "driver_reference")}},
            indent=2) + "\n")
        (output / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "native", "diagnostic_fixture": False,
            "case_id": case_id, "physical_acceptance_claimed": False}, indent=2) + "\n")
        complete = True
        return {"case_id": case_id, "frames": FRAMES, "requested_target_x_m": target,
                "physical_acceptance_claimed": False}
    except BaseException as error:
        if output.exists():
            (output / "native-run-status.json").write_text(json.dumps({
                "errors": [str(error)], "frames_complete": complete,
                "physical_acceptance_claimed": False}, indent=2) + "\n")
        raise
    finally:
        cleanup_errors = []
        if capture is not None:
            try:
                capture.close(confirmed=complete)
            except Exception as error:
                cleanup_errors.append("capture close: " + str(error))
        for process in encoders.values():
            try:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            except Exception as error:
                cleanup_errors.append("encoder cleanup: " + str(error))
        for actor in reversed(owned):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
                actor.destroy()
            except Exception as error:
                cleanup_errors.append("actor cleanup: " + str(error))
        try:
            restoration = restore(client, prior) if changed else {"restored": True, "world_unchanged": True}
        except Exception as error:
            cleanup_errors.append("world restoration: " + str(error))
            restoration = {"restored": False, "errors": cleanup_errors}
        if complete and not cleanup_errors and restoration.get("restored"):
            seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                         encoder_exit_codes={name: process.returncode for name, process in encoders.items()},
                         context={"case_id": case_id, "candidate_id": config.get("candidate_id", "primary"),
                                  "safety_zone_review": "pending_original_source"})
        elif cleanup_errors and output.exists():
            (output / "native-cleanup-status.json").write_text(json.dumps({
                "errors": cleanup_errors, "restoration": restoration,
                "capture_complete": complete, "sealed": False}, indent=2) + "\n")
        if cleanup_errors and sys.exc_info()[0] is None:
            raise RuntimeError("Native cleanup or world restoration failed: " + "; ".join(cleanup_errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case-id")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check()))
    elif args.output_dir:
        config = json.loads((Path(__file__).parent / "config.json").read_text())
        case = args.case_id or config.get("selected_case_id")
        if case != config.get("selected_case_id"):
            raise ValueError("Native case differs from materialized bundle")
        print(json.dumps(execute(case, args.output_dir, args.host, args.port)))
    else:
        parser.error("Supply --output-dir for Native capture")
