"""First exact C125745(1) stop-sign construction and original-source capture.

`--check` is CPU only.  Capture is reserved for a separately authorized Native
operator and refuses a map or sign different from the hash-bound site packet.
"""

import argparse
from contextlib import ExitStack
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon

from crossing_measurements import capture_sample
from source_cameras import CAMERAS, SourceVideo, matching_frame, source_cameras
from stop_entry_control import step_ego, step_other
from stop_sign_control import construct_candidate, load_site


ASSIGNMENT = "testing__C125745__NRS-484B-250-1__motor_vehicle_driver"
CASE = ASSIGNMENT + "__stop_sign_other_first"
FRAMES = 900
RATE_HZ = 20


def check_plan(plan_path, config_path=None):
    plan = json.loads(Path(plan_path).read_text())
    if (plan.get("assignment_id") != ASSIGNMENT or
            plan.get("law_id") != "NRS-484B-250-1" or
            plan.get("cell_id") != "C125745" or
            plan.get("actor") != "motor_vehicle_driver" or
            CASE not in [case.get("case_id") for case in plan.get("cases", [])]):
        raise ValueError("Exact subsection (1) other-first case required")
    site = load_site()
    if set(site["camera_poses"]) != set(CAMERAS) or site["review_status"] != "synthetic_cpu_candidate":
        raise ValueError("Four source cameras and honest site provenance required")
    if config_path is not None:
        config = json.loads(Path(config_path).read_text())
        if (config.get("assignment_id") != ASSIGNMENT or
                config.get("selected_case_id") != CASE or
                config.get("law_id") != "NRS-484B-250-1" or
                config.get("cell_id") != "C125745" or
                config.get("actor") != "motor_vehicle_driver" or
                config.get("rate_hz") != RATE_HZ or config.get("frames") != FRAMES or
                config.get("duration_s") != FRAMES / RATE_HZ or
                not isinstance(config.get("required_atoms"), list) or
                not config.get("recording_description", {}).get("channels") or
                config.get("site_packet") != {"path": "site.json",
                                               "sha256": site["site_source_sha256"]}):
            raise ValueError("Exact source-bound C125745(1) config required")
    return site


def _transform(carla, pose):
    return carla.Transform(carla.Location(x=pose[0], y=pose[1], z=pose[2]),
                           carla.Rotation(yaw=pose[3],
                                          pitch=pose[4] if len(pose) > 4 else 0,
                                          roll=pose[5] if len(pose) > 5 else 0))


def _speed(actor):
    v = actor.get_velocity()
    speed = math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
    if not math.isfinite(speed):
        raise ValueError("Finite Native actor speed required")
    return speed


def _body_inside(actor, polygon):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) < 4:
        raise ValueError("Complete other body required")
    body = MultiPoint([(v.x, v.y) for v in vertices]).convex_hull
    if body.area <= 0:
        raise ValueError("Nondegenerate other body required")
    return body.intersects(polygon), body.distance(polygon)


def _control(carla, actor, throttle, brake, target):
    pose = actor.get_transform()
    bearing = math.atan2(target[1] - pose.location.y, target[0] - pose.location.x)
    error = (bearing - math.radians(pose.rotation.yaw) + math.pi) % (2 * math.pi) - math.pi
    distance = max(4.0, math.hypot(target[0] - pose.location.x, target[1] - pose.location.y))
    curvature = 2 * math.sin(error) / distance
    steer = max(-1.0, min(1.0, -math.atan(2.8 * curvature) / math.radians(35)))
    command = carla.VehicleControl(throttle=throttle, brake=brake, steer=steer)
    actor.apply_control(command)
    return {"throttle": throttle, "brake": brake, "steer": steer}


def _context(site, ego_road, other_road):
    return {
        "native_map_id": site["native_map_name"],
        "intersection_id": site["junction_id"],
        "ego_highway_id": site["highway_ids"]["ego"],
        "other_highway_id": site["highway_ids"]["other"],
        "ego_road_id": ego_road, "other_road_id": other_road,
        "native_stop_sign_id": site["stop_sign_native_id"],
        "sign_governance_source": site["sign_erection_source"],
        "stop_sign_video_source": site["camera_plan_source"],
        "intersection_polygon_source": site["crossing_source"],
        "intersection_polygon_xy_m": site["crossing_polygon_xy_m"],
        "stop_sign_governed_road_id": ego_road,
        "stop_sign_erected": True,
        "review_status": "synthetic_cpu_candidate",
        "physical_acceptance_claimed": False,
        "legal_conclusion": "unresolved",
    }


def capture(args, site, config):
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as save_world, restore

    output = Path(args.output_dir).resolve()
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("Use runtime.py capture for the exact construction")
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = save_world(client)
    writers = {}
    helper = None
    frames = 0
    succeeded = False
    try:
        world = client.get_world()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1 / RATE_HZ
        world.apply_settings(settings)
        world_map = world.get_map()
        if world_map.name != site["native_map_name"]:
            raise ValueError("Native map differs from hash-bound C125745 site")
        transforms = {name: _transform(carla, site[name]) for name in
                      ("ego_approach", "ego_entry", "other_approach", "other_entry")}
        transforms["ego_sign_check"] = _transform(carla,
            site["ego_stop_line_xy_m"] +
            [site["ego_approach"][2], site["ego_approach"][3]])
        blueprints = world.get_blueprint_library().filter("vehicle.*")
        if not blueprints:
            raise ValueError("Native vehicle blueprint missing")
        with construct_candidate(world, site, transforms, blueprints[0]) as pair:
            ego, other, sign = pair["ego"], pair["other"], pair["stop_sign"]
            if sign.id != site["stop_sign_native_id"]:
                raise ValueError("Native stop sign differs from reviewed identity")
            road_ids = pair["approach_road_ids"]
            context = _context(site, road_ids["ego"], road_ids["other"])
            (output / "junction_context.json").write_text(json.dumps(context, indent=2) + "\n")
            polygon = Polygon(site["crossing_polygon_xy_m"])
            camera_transforms = {name: _transform(carla, pose)
                                 for name, pose in site["camera_poses"].items()}
            with source_cameras(world, ego, camera_transforms) as queues:
                with ExitStack() as stack:
                    history = stack.enter_context((output / "crossing_history.jsonl").open("x", buffering=1))
                    controls = stack.enter_context((output / "controller_history.jsonl").open("x", buffering=1))
                    frame_map = stack.enter_context(FrameMap(output / "video_frames.jsonl"))
                    for name, (width, height) in CAMERAS.items():
                        writers[name] = SourceVideo(output / (name + ".mkv"), width, height)
                    helper = PipelineCapture(client, ego, output, CASE,
                                             required_observations=config["required_atoms"])
                    stopped_frames = 0
                    other_entered = False
                    try:
                        for index in range(FRAMES):
                            inside, distance = _body_inside(other, polygon)
                            other_entered = other_entered or inside
                            clear = other_entered and not inside and distance > 8
                            ego_pose = ego.get_transform()
                            stop_x, stop_y = site["ego_stop_line_xy_m"]
                            stop_distance = (stop_x - ego_pose.location.x)
                            ego_throttle, ego_brake, stopped_frames, phase = step_ego(
                                stop_distance, _speed(ego), stopped_frames, clear)
                            other_throttle, other_brake, other_phase = step_other(
                                _speed(other), config["other_release_frame"], index)
                            commands = {
                                "ego": _control(carla, ego, ego_throttle, ego_brake, (30, 0)),
                                "other": _control(carla, other, other_throttle, other_brake, (15, 15)),
                            }
                            world.tick()
                            snapshot = world.get_snapshot()
                            frame = snapshot.frame
                            for name in CAMERAS:
                                image = matching_frame(queues[name], frame)
                                writers[name].write(image, frame)
                            helper.capture(frame, snapshot.timestamp.elapsed_seconds)
                            row = capture_sample(snapshot, world_map, ego, other, sign,
                                                 site["crossing_polygon_xy_m"],
                                                 site["junction_id"], road_ids)
                            history.write(json.dumps(row, allow_nan=False) + "\n")
                            frame_map.append(frame, row["time_s"])
                            controls.write(json.dumps({"frame": frame, "time_s": row["time_s"],
                                "ego_phase": phase, "other_phase": other_phase,
                                "other_entered": other_entered, "other_conflict_clear": clear,
                                "commands": commands}, allow_nan=False) + "\n")
                            frames += 1
                    except BaseException:
                        helper.close(confirmed=False)
                        helper = None
                        raise
                    else:
                        helper.close()
                        helper = None
        if frames != FRAMES:
            raise ValueError("Incomplete original Native capture")
        for writer in writers.values():
            writer.close()
        succeeded = True
    finally:
        if helper is not None:
            helper.close(confirmed=False)
        if not succeeded:
            for writer in writers.values():
                if not writer.closed:
                    try:
                        writer.close()
                    except Exception:
                        pass
        restoration = restore(client, saved)
        if succeeded:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: writer.process.returncode for name, writer in writers.items()},
                         context={"physical_acceptance_claimed": False,
                                  "site_source_sha256": site["site_source_sha256"]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default=str(Path(__file__).with_name("case-plan.json")))
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text()) if Path(args.config).is_file() else None
    site = check_plan(args.plan, args.config if config is not None else None)
    if args.check:
        print(json.dumps({"assignment_id": ASSIGNMENT, "case_id": CASE,
                          "planned_frames": FRAMES, "rate_hz": RATE_HZ,
                          "source_cameras": list(CAMERAS), "site_review_status": site["review_status"],
                          "cpu_check_passed": True, "carla_started": False,
                          "physical_acceptance_claimed": False}))
        return
    if not args.output_dir:
        raise ValueError("--output-dir required for Native capture")
    if config is None:
        raise ValueError("Exact config.json required for Native capture")
    if type(config.get("other_release_frame")) is not int or not 0 <= config["other_release_frame"] < FRAMES:
        raise ValueError("Other release frame outside planned capture")
    capture(args, site, config)


if __name__ == "__main__":
    main()
