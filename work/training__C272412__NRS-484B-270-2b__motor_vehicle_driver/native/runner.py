"""Original Native four-view capture for the exact C272412 scooter pass plan.

The CPU check does not import CARLA. Original motion, lane availability, pixels,
reasonable safety and due care remain subject to saved-source review.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess

from scene import PASS_TARGETS_M, FRAMES, HZ, check as scene_check, open_drive, target


CAMERAS = (("overview", 1920, 1080, -10, -18, 28),
           ("approach", 1280, 720, -43, -12, 8),
           ("reference_corner", 1280, 720, 0, -12, 8),
           ("driver_reference", 1280, 720, 25, -12, 8))


def check(case_suffix):
    if case_suffix not in PASS_TARGETS_M:
        raise ValueError("Exact case suffix required")
    proof = scene_check()
    if len(CAMERAS) != 4 or len({c[0] for c in CAMERAS}) != 4:
        raise ValueError("Four distinct cameras required")
    return {"passed": True, "case_suffix": case_suffix, "scene": proof,
            "camera_names": [c[0] for c in CAMERAS], "frames": FRAMES,
            "duration_s": FRAMES / HZ, "native_imported": False,
            "physical_or_legal_acceptance": False}


def survey_check(survey):
    """Require an original operator source for the electric-scooter actor."""
    required = ("source_path", "device_blueprint", "device_blueprint_source",
                "device_subtype_source", "scooter_classification_source",
                "scooter_handlebars_source", "scooter_electric_motor_source",
                "scooter_riding_design_source", "scooter_mass_source",
                "scooter_motor_max_speed_source", "rider_identity_source")
    for key in required:
        if not survey.get(key):
            raise ValueError("Missing original scooter survey source: " + key)
    if survey.get("device_subtype") != "electric_scooter":
        raise ValueError("Surveyed actor is not an electric scooter")
    if any(token in survey["device_blueprint"].lower() for token in ("bicycle", "bike")):
        raise ValueError("Bicycle blueprint cannot establish scooter identity")
    mass = survey.get("scooter_rider_excluded_mass_lb")
    speed = survey.get("scooter_motor_only_max_mph")
    if type(mass) not in (float, int) or not 0 < mass <= 100:
        raise ValueError("Original scooter mass classification missing or out of bounds")
    if type(speed) not in (float, int) or not 0 < speed <= 20:
        raise ValueError("Original scooter motor speed classification missing or out of bounds")
    return survey


def load_survey(path, case_suffix):
    if not path:
        raise ValueError("SCENARIO_CONTEXT_SURVEY required for original scooter identity")
    survey = survey_check(json.loads(Path(path).read_text()))
    if case_suffix == "exception_1_2" and (not survey.get("no_passing_zone_source") or
                                           survey.get("no_passing_zone_designated") is not True):
        raise ValueError("Original affirmative no-passing-zone designation source required")
    if case_suffix.startswith("exception_") and not survey.get("cited_213_217_applicability_source"):
        raise ValueError("Original NRS 484B.213/.217 applicability source required")
    return survey


def actor_row(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    corners = sorted({(round(p.x, 5), round(p.y, 5))
                      for p in actor.bounding_box.get_world_vertices(transform)})
    if len(corners) != 4:
        raise RuntimeError("Original actor body corners unavailable")
    return {"actor_id": actor.id, "blueprint_id": actor.type_id,
            "center_xy_m": [transform.location.x, transform.location.y],
            "body_xy_m": [list(xy) for xy in corners],
            "heading_deg": transform.rotation.yaw,
            "speed_mps": math.hypot(velocity.x, velocity.y)}


def steering_command(lateral_error_m, observed_yaw_deg):
    """CARLA negative steering requests leftward (+y) movement at yaw zero."""
    return max(-.35, min(.35, -.12 * lateral_error_m + observed_yaw_deg / 20))


def execute(case_suffix, case_id, output, host, port):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.media import compose_four_views
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot, restore

    check(case_suffix)
    if not case_id or not case_id.endswith("__" + case_suffix):
        raise ValueError("Exact case ID and suffix differ")
    survey_path = os.environ.get("SCENARIO_CONTEXT_SURVEY")
    survey = load_survey(survey_path, case_suffix)
    output = Path(output).resolve()
    if not output.is_dir() or (output / "participant-poses.jsonl").exists():
        raise ValueError("Materialized original attempt must be fresh")
    client = carla.Client(host, port)
    client.set_timeout(180)
    saved = snapshot(client)
    old = client.get_world()
    if saved["settings"].synchronous_mode or any(a.type_id.startswith(
            ("vehicle.", "walker.", "sensor.", "controller.")) for a in old.get_actors()):
        raise RuntimeError("Exclusive idle asynchronous Native world required")
    output.mkdir(parents=True, exist_ok=True)
    owned = []
    camera_queues = {}
    encoders = {}
    capture = None
    changed = False
    complete = False
    try:
        world = client.generate_opendrive_world(open_drive(case_suffix == "exception_1_2"), carla.OpendriveGenerationParameters(
            vertex_distance=.5, max_road_length=50, wall_height=0, additional_width=0,
            smooth_junctions=False, enable_mesh_visibility=True,
            enable_pedestrian_navigation=False))
        changed = True
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / HZ
        settings.substepping = True
        settings.max_substep_delta_time = .01
        settings.max_substeps = 10
        world.apply_settings(settings)
        road = world.get_map()
        for x, y, expected in ((-40, -1.75, -1), (-40, 1.75, 1)):
            waypoint = road.get_waypoint(carla.Location(x=x, y=y, z=1),
                                         project_to_road=True, lane_type=carla.LaneType.Driving)
            if waypoint is None or waypoint.lane_id != expected:
                raise RuntimeError("Original single-lane-per-direction Native readback differs")
        if len(road.get_topology()) < 2:
            raise RuntimeError("Native lane topology unavailable")
        library = world.get_blueprint_library()
        def spawn(blueprint_id, role, x, y):
            bp = library.find(blueprint_id)
            bp.set_attribute("role_name", role)
            actor = world.spawn_actor(bp, carla.Transform(carla.Location(x=x, y=y, z=1),
                                                          carla.Rotation(yaw=0)))
            owned.append(actor)
            return actor
        ego = spawn("vehicle.tesla.model3", "c272412_driver", -30, -1.75)
        scooter = spawn(survey["device_blueprint"], "c272412_scooter", -10, -2.3)
        capture = PipelineCapture(client, ego, output, case_id,
                                  visibility=False, required_observations=[])
        for name, width, height, x, y, z in CAMERAS:
            bp = library.find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(width))
            bp.set_attribute("image_size_y", str(height))
            bp.set_attribute("fov", "85")
            bp.set_attribute("sensor_tick", ".05")
            camera = world.spawn_actor(bp, carla.Transform(
                carla.Location(x=x, y=y, z=z),
                carla.Rotation(pitch=-50 if z > 15 else -25)))
            owned.append(camera)
            frames = queue.Queue()
            camera.listen(frames.put)
            camera_queues[name] = frames
            process = subprocess.Popen([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}",
                "-r", str(HZ), "-i", "-", "-frames:v", str(FRAMES),
                "-c:v", "ffv1", "-level", "1", str(output / (name + ".mkv"))],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            encoders[name] = process
        first_time = None
        with FrameMap(output / "video_frames.jsonl") as mapping, \
                (output / "participant-poses.jsonl").open("x") as poses, \
                (output / "trace.jsonl").open("x") as trace:
            for index in range(FRAMES):
                intended = target(case_suffix, index)
                observed = actor_row(ego)
                lateral_error = intended.ego_y_m - observed["center_xy_m"][1]
                speed_error = 4 - observed["speed_mps"]
                ego.apply_control(carla.VehicleControl(
                    throttle=max(0, min(.6, .25 + .12 * speed_error)),
                    brake=max(0, min(.5, -.15 * speed_error)),
                    steer=steering_command(lateral_error, observed["heading_deg"])))
                scooter.set_target_velocity(carla.Vector3D(x=2, y=0, z=0))
                frame = world.tick()
                stamp = world.get_snapshot()
                if stamp.frame != frame:
                    raise RuntimeError("Native frame/snapshot join differs")
                first_time = stamp.timestamp.elapsed_seconds if first_time is None else first_time
                elapsed = stamp.timestamp.elapsed_seconds - first_time
                capture.capture(frame, elapsed)
                e, c = actor_row(ego), actor_row(scooter)
                poses.write(json.dumps({"frame": frame, "video_frame": index,
                                        "time_s": elapsed, "ego": e, "scooter": c,
                                        "authored_center_marking": "solid" if case_suffix == "exception_1_2" else "broken"}) + "\n")
                trace.write(json.dumps({"frame": frame, "time_s": elapsed,
                                        "position_m": [*e["center_xy_m"], 1],
                                        "heading_deg": e["heading_deg"],
                                        "speed_mps": e["speed_mps"]}) + "\n")
                joined = {}
                for name in camera_queues:
                    image = camera_queues[name].get(timeout=30)
                    while image.frame < frame:
                        image = camera_queues[name].get(timeout=30)
                    if image.frame != frame:
                        raise RuntimeError("Original camera/frame join differs")
                    encoders[name].stdin.write(image.raw_data)
                    joined[name] = image.frame
                mapping.append(frame, elapsed, camera_native_frames=joined)
        for name, process in encoders.items():
            process.stdin.close()
            stderr = process.stderr.read()
            if process.wait(timeout=180):
                raise RuntimeError("Camera encoding failed: " + name + ": " + stderr.decode()[-400:])
        compose_four_views({name: output / (name + ".mkv") for name in camera_queues},
                           output / "video_frames.jsonl", output / "raw.mkv")
        (output / "road.xodr").write_text(road.to_opendrive())
        (output / "pass-context.json").write_text(json.dumps({
            "case_id": case_id, "statutory_subject": "electric_scooter",
            "source_kind": "native_original",
            "scooter_actor_id": scooter.id, "scooter_blueprint_id": scooter.type_id,
            "survey_path": str(Path(survey_path).resolve()),
            "survey_sha256": hashlib.sha256(Path(survey_path).read_bytes()).hexdigest(),
            "same_direction_lane_count_authored": 1,
            "center_marking_authored": "solid" if case_suffix == "exception_1_2" else "broken",
            "center_crossing_and_safety_review": "pending_original_readback_and_context"}) + "\n")
        complete = True
    finally:
        if capture is not None:
            capture.close(confirmed=complete)
        for process in encoders.values():
            if process.poll() is None:
                process.kill()
                process.wait()
        for actor in reversed(owned):
            try:
                actor.stop() if hasattr(actor, "stop") else None
                actor.destroy()
            except Exception:
                pass
        restoration = restore(client, saved) if changed else {"restored": True}
        if complete:
            seal_capture(output, frames=FRAMES, restoration=restoration, errors=[],
                         encoder_exit_codes={k: v.returncode for k, v in encoders.items()},
                         context={"case_id": case_id, "source_review": "pending"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-suffix", choices=PASS_TARGETS_M)
    parser.add_argument("--case-id")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config_path = Path("config.json")
    config = json.loads(config_path.read_text()) if config_path.is_file() else {}
    suffix = args.case_suffix or config.get("case_suffix")
    case_id = args.case_id or config.get("case_id")
    if args.check:
        print(json.dumps(check(suffix)))
    else:
        if args.output_dir is None:
            parser.error("--output-dir required for Native execution")
        execute(suffix, case_id, args.output_dir, args.host, args.port)
