"""Three-vehicle Native capture candidate for the C24811 blind signal branch.

Dispatch through runtime.py into an ignored .runtime-work attempt. CPU --check
validates authored inputs only; Native motion and pixels are never inferred.
"""

import argparse
import json
import math
import os
from contextlib import ExitStack
from pathlib import Path
from queue import Queue

from blind_site import validate as validate_site
from blind_signal_measurements import STOP_LINE_TOLERANCE_M
from interaction_routes import release_permission, validate as validate_routes
from occluder_construction import spawn_matching_occluder
from signal_control import find_entrance_lights, request_all_state
from source_cameras import (CAMERAS, SIZES, ffv1_writer, source_camera_frame,
                            source_cameras, validate_plan as validate_cameras)
from three_vehicle_sources import source_row
from vehicle_control import RollingController, StopController


ROOT = Path(__file__).resolve().parent
PREFIX = "testing__C24811__NRS-484B-250-4__motor_vehicle_driver__"


def check():
    site = validate_site(ROOT/"blind-site-candidate.json")
    routes = validate_routes(ROOT/"interaction-routes.json")
    cameras = validate_cameras(ROOT/"capture-plan.json")
    return {"site": site, "routes": routes, "cameras": cameras,
            "native_capture_verified": False}


def _steer(actor, targets):
    pose = actor.get_transform()
    location = pose.location
    nearest = min(range(len(targets)), key=lambda index:
                  math.hypot(targets[index][0]-location.x,
                             targets[index][1]-location.y))
    target = targets[min(nearest+1, len(targets)-1)]
    desired = math.degrees(math.atan2(target[1]-location.y, target[0]-location.x))
    error = (desired-pose.rotation.yaw+180)%360-180
    return max(-1.0, min(1.0, error/45.0))


def _feedback(row, entered, cleared, intersection, previous):
    from shapely.geometry import MultiPoint

    inside = {}
    for role in ("ego", "earlier", "occupant"):
        body = MultiPoint(row[role]["body_vertices_xy_m"]).convex_hull
        inside[role] = body.intersects(intersection)
        if inside[role]:
            entered[role] = True
        elif entered[role]:
            cleared[role] = True
    ego_body = MultiPoint(row["ego"]["body_vertices_xy_m"]).convex_hull
    occupant_body = MultiPoint(row["occupant"]["body_vertices_xy_m"]).convex_hull
    return {"observed_ego_halt": previous["observed_ego_halt"] or (
            row["ego"]["speed_mps"] == 0 and
            0 <= row["ego"]["front_to_stop_line_signed_m"] <= STOP_LINE_TOLERANCE_M),
            "observed_earlier_halt": previous["observed_earlier_halt"] or (
            row["earlier"]["speed_mps"] == 0 and
            0 <= row["earlier"]["front_to_stop_line_signed_m"] <= STOP_LINE_TOLERANCE_M),
            "observed_occupant_halt": previous["observed_occupant_halt"] or (
            row["occupant"]["speed_mps"] == 0 and
            0 <= row["occupant"]["front_to_stop_line_signed_m"] <= STOP_LINE_TOLERANCE_M),
            "observed_occupant_entry": entered["occupant"],
            "observed_earlier_clearance": cleared["earlier"],
            "ego_occupant_body_separation_m": ego_body.distance(occupant_body)}


def _native_point(carla, xy):
    return carla.Location(x=xy[0], y=xy[1], z=1.5)


def capture(args):
    """Attempt one original Native capture; do not mark it accepted on CPU."""
    if not args.case_id.startswith(PREFIX):
        raise ValueError("Exact C24811 case ID required")
    name = args.case_id[len(PREFIX):]
    check()
    site = json.loads((ROOT/"blind-site-candidate.json").read_text())
    routes = json.loads((ROOT/"interaction-routes.json").read_text())
    camera_plan = json.loads((ROOT/"capture-plan.json").read_text())
    if name not in routes["case_controls"]:
        raise ValueError("Unsupported selected C24811 case")
    mode = routes["case_controls"][name]
    if mode["signal"] == "Off":
        if args.operative_state is not None:
            raise ValueError("Operative state applies only to operative case")
        signal_state = "Off"
    else:
        if args.operative_state not in ("Green", "Yellow", "Red"):
            raise ValueError("Explicit operative state required")
        signal_state = args.operative_state
    if not args.occluder_blueprint and args.occluder_filter != "vehicle.*":
        raise ValueError("Bounded Native occluder blueprint filter required")
    output = Path(args.output_dir).resolve()
    repo = ROOT.parents[1]
    runtime_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    if (not runtime_root or
            not Path(runtime_root).resolve().is_relative_to(repo/".runtime-work") or
            not output.is_relative_to(Path(runtime_root).resolve()) or
            not (output/"construction.json").is_file()):
        raise ValueError("Use runtime.py to materialize an ignored exact attempt")
    runtime_config = json.loads((output/"config.json").read_text())
    if runtime_config.get("selected_case_id") != args.case_id or not runtime_config.get("required_atoms"):
        raise ValueError("Materialized exact case and atom contract required")

    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import restore, snapshot
    from shapely.geometry import Polygon

    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    saved = snapshot(client)
    world = None
    actors = {}
    collector = None
    frames = 0
    error = None
    try:
        world = client.generate_opendrive_world((ROOT/site["map"]["path"]).read_text())
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 1/camera_plan["rate_hz"]
        world.apply_settings(settings)
        blueprints = world.get_blueprint_library().filter("vehicle.*")
        if not blueprints:
            raise ValueError("No Native vehicle blueprint")
        for role in ("ego", "earlier", "occupant"):
            road, lane, station = routes["vehicles"][role]["spawn_road_lane_s"]
            waypoint = world.get_map().get_waypoint_xodr(road, lane, station)
            if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (road, lane):
                raise ValueError("Native approach differs from authored route: " + role)
            pose = waypoint.transform
            pose.location.z += 0.5
            actor = world.try_spawn_actor(blueprints[0], pose)
            if actor is None:
                raise ValueError("Native three-vehicle spawn failed: " + role)
            actors[role] = actor
        lanes = [[site["entrances"][role]["road_id"], site["entrances"][role]["lane_id"]]
                 for role in ("ego", "other")]
        lights = find_entrance_lights(world, lanes)
        desired = getattr(carla.TrafficLightState, signal_state)
        candidates = ([world.get_blueprint_library().find(args.occluder_blueprint)]
                      if args.occluder_blueprint else
                      list(world.get_blueprint_library().filter(args.occluder_filter)))
        occluder_pose = carla.Transform(
            carla.Location(x=args.occluder_x, y=args.occluder_y, z=args.occluder_z),
            carla.Rotation(yaw=args.occluder_yaw))
        rays = {role: (_native_point(carla, site["entrances"][role]["viewpoint_xy_m"]),
                       _native_point(carla, site["entrances"][role]["target_vehicle_xy_m"]))
                for role in ("ego", "other")}
        corridors = {role: [_native_point(carla, point) for point in
                            site["entrances"][role]["vehicle_corridor_centerline_xy_m"]]
                     for role in ("ego", "other")}
        polygon = Polygon(site["intersection_polygon_xy_m"])
        entered = {role: False for role in actors}
        cleared = {role: False for role in actors}
        observed = {"observed_ego_halt": False, "observed_earlier_halt": False,
                    "observed_occupant_halt": False, "observed_occupant_entry": False,
                    "observed_earlier_clearance": False,
                    "ego_occupant_body_separation_m": 0}
        controllers = {}
        for role in actors:
            policy = mode["ego_stop"] if role == "ego" else (
                mode["earlier_stop"] if role == "earlier" else "full_halt")
            speed = (mode.get("ego_target_speed_override_mps", routes["vehicles"][role]["target_speed_mps"])
                     if role == "ego" else routes["vehicles"][role]["target_speed_mps"])
            controllers[role] = (RollingController(speed) if policy in ("rolling", "no_prior_halt")
                                 else StopController(100 if role == "earlier" else 0, speed))
        with spawn_matching_occluder(world, candidates, occluder_pose, rays, corridors,
                                     site["occluder"]["minimum_corridor_clearance_m"]) as realized_occluder:
            with request_all_state(world, lights, desired):
                with source_cameras(world, actors["ego"], carla, camera_plan) as sensors:
                    queues = {camera: Queue() for camera in CAMERAS}
                    for camera, sensor in sensors.items():
                        sensor.listen(lambda image, camera=camera: queues[camera].put(image))
                    with ExitStack() as stack:
                        writers = {camera: stack.enter_context(
                            ffv1_writer(output/(camera+".mkv"), SIZES[camera]))
                            for camera in CAMERAS}
                        frame_map = stack.enter_context(FrameMap(output/"video_frames.jsonl"))
                        history = stack.enter_context((output/"vehicle_signal_history.jsonl").open("x", buffering=1))
                        collector = PipelineCapture(client, actors["ego"], output, args.case_id,
                                                    required_observations=runtime_config["required_atoms"])
                        try:
                            for index in range(camera_plan["duration_s"]*camera_plan["rate_hz"]):
                                observed["scheduled_frame"] = index >= 100
                                for role, actor in actors.items():
                                    route = routes["vehicles"][role]
                                    verts = actor.bounding_box.get_world_vertices(actor.get_transform())
                                    from three_vehicle_sources import signed_front_distance
                                    signed = signed_front_distance([[v.x,v.y] for v in verts],
                                        route["stop_line_point_xy_m"], route["upstream_normal_xy"])
                                    release = release_permission(routes, name, role, observed)
                                    controllers[role].step(carla, actor, index, signed,
                                        steer=_steer(actor,route["target_xy_m"]),
                                        release_condition=release)
                                world.tick()
                                snap = world.get_snapshot()
                                if any(light.get_state() != desired for light in lights):
                                    raise ValueError("Native governing signal changed during capture")
                                for camera in CAMERAS:
                                    writers[camera](source_camera_frame(queues[camera], snap.frame))
                                frame_map.append(snap.frame, snap.timestamp.elapsed_seconds)
                                collector.capture(snap.frame, snap.timestamp.elapsed_seconds)
                                row = source_row(int(snap.frame),float(snap.timestamp.elapsed_seconds),
                                    site["junction_id"], lights, actors, routes["vehicles"])
                                observed.update(_feedback(row,entered,cleared,polygon,observed))
                                history.write(json.dumps(row,allow_nan=False)+"\n")
                                frames += 1
                        finally:
                            collector.close(confirmed=frames == camera_plan["duration_s"]*camera_plan["rate_hz"])
                            collector = None
        context = {"native_map_id": "C24811 authored blind junction candidate",
                   "intersection_id": site["junction_id"],
                   "signal_head_video_source": "overview, approach, reference_corner, driver_reference original streams",
                   "all_entrances_source": site["map"]["sha256"],
                   "stop_line_source": site["map"]["sha256"],
                   "occluder_geometry_source": "realized Native actor bounding box and four original camera streams",
                   "occluder_realization": {key:value for key,value in realized_occluder.items()
                                             if key != "actor"},
                   "sight_ray_source": "authored viewpoints and realized footprint",
                   "stop_line_exists": True,
                   "signal_heads": [{"native_id": light.id, "entrance_id": role,
                                     "installed": True, "uncovered": True,
                                     "physical_visibility_verified": False}
                                    for role,light in zip(("ego","other"),lights)],
                   "intersection_polygon_xy_m": site["intersection_polygon_xy_m"],
                   "physical_head_visibility_verified": False}
        (output/"junction_context.json").write_text(json.dumps(context,indent=2)+"\n")
    except BaseException as exc:
        error = exc
        raise
    finally:
        if collector is not None:
            collector.close(confirmed=False)
        for actor in reversed(list(actors.values())):
            actor.destroy()
        restoration = restore(client,saved)
        if error is None:
            seal_capture(output,frames=frames,restoration=restoration,errors=[],
                         encoder_exit_codes={camera:0 for camera in CAMERAS},
                         context={"native_site_candidate":True,"legal_review_verified":False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--case-id")
    parser.add_argument("--operative-state", choices=("Green","Yellow","Red"))
    parser.add_argument("--occluder-blueprint")
    parser.add_argument("--occluder-filter", default="vehicle.*")
    parser.add_argument("--occluder-x", type=float, default=-12)
    parser.add_argument("--occluder-y", type=float, default=-12)
    parser.add_argument("--occluder-z", type=float, default=0)
    parser.add_argument("--occluder-yaw", type=float, default=0)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check(),indent=2))
    elif args.output_dir and args.case_id:
        capture(args)
    else:
        parser.error("--check or exact --output-dir and --case-id required")


if __name__ == "__main__":
    main()
