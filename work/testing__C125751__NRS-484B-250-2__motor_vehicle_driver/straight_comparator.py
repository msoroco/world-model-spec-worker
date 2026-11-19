"""Same-site straight-route construction for the C125751 turn comparison.

The straight exit is an independently sourced route. This module checks the
controlled difference before any Native actor is spawned. Angle bounds are
engineering route checks, not legal definitions of a turn.
"""

from contextlib import ExitStack, contextmanager
import copy
import hashlib
import json
import math
from pathlib import Path
from queue import Empty, Queue

from shapely.geometry import Point, Polygon

from camera_setup import SIZES, source_cameras
from camera_encoder import FFV1Writer
from capture_sources import _actor, _native_state, _stop_state
from route_control import steering_command
from yield_controller import apply_speed_control


FIXED_SITE_FIELDS = (
    "native_map_name", "native_junction_id", "crossing_polygon_xy_m",
    "crossing_polygon_source", "approach_headings_deg",
    "expected_approach_lanes", "approach_geometry_source",
    "governed_signal_ids", "device_inventory_source",
    "selected_stop_references", "cameras",
)
ROLES = ("ego", "other")
COMPARATOR_CASE = "testing__C125751__NRS-484B-250-2__motor_vehicle_driver__opposite_straight_comparator"


def verify_route_source(reference):
    """Read the retained original route document before building a comparator."""
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise ValueError("Original straight-route source path and hash required")
    path = Path(reference["path"])
    digest = reference["sha256"]
    if (not path.is_file() or not isinstance(digest, str) or len(digest) != 64 or
            hashlib.sha256(path.read_bytes()).hexdigest() != digest):
        raise ValueError("Straight-route source missing or changed")
    source = json.loads(path.read_text())
    if (source.get("format") != "worker-c125751-straight-route-source-v1" or
            source.get("case_id") != COMPARATOR_CASE or
            source.get("site_baseline") != "opposite_left_turn" or
            source.get("route_role") != "ego" or
            type(source.get("diagnostic_only")) is not bool or
            not source.get("source_basis")):
        raise ValueError("Exact source identity for straight comparator required")
    return source


def _bearing(start, end):
    if (not isinstance(start, list) or not isinstance(end, list) or
            len(start) != 2 or len(end) != 2 or
            any(type(value) not in (int, float) or not math.isfinite(value)
                for value in start + end)):
        raise ValueError("Finite sourced XY route points required")
    dx, dy = end[0] - start[0], end[1] - start[1]
    if math.hypot(dx, dy) < .1:
        raise ValueError("Distinct sourced route points required")
    return math.degrees(math.atan2(dy, dx))


def _angle(start, end):
    return (end - start + 180) % 360 - 180


def straight_site(left_site, straight_ego_route, route_source):
    """Keep all source site facts except ego's exit route fixed.

    The other driver's route and both approach points remain byte-equivalent
    JSON values. A caller must retain the straight route's original map source.
    """
    source = verify_route_source(route_source)
    if straight_ego_route != source.get("route_xy_m"):
        raise ValueError("Straight route differs from retained original source")
    if not isinstance(left_site, dict) or any(key not in left_site for key in FIXED_SITE_FIELDS):
        raise ValueError("Complete reviewed left-turn site required")
    old_routes = left_site.get("routes")
    if not isinstance(old_routes, dict) or set(old_routes) != set(ROLES):
        raise ValueError("Two reviewed original routes required")
    old_ego = old_routes["ego"]
    if (not isinstance(old_ego, list) or len(old_ego) < 4 or
            not isinstance(straight_ego_route, list) or len(straight_ego_route) < 4 or
            straight_ego_route[:3] != old_ego[:3] or
            straight_ego_route == old_ego):
        raise ValueError("Straight comparator must retain ego approach and change exit")
    polygon = Polygon(left_site["crossing_polygon_xy_m"])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Valid same-site crossing polygon required")
    for label, route in (("left", old_ego), ("straight", straight_ego_route),
                         ("opposing", old_routes["other"])):
        if not isinstance(route, list) or len(route) < 4:
            raise ValueError("Complete " + label + " route required")
        for point in route:
            if (not isinstance(point, list) or len(point) != 2 or
                    any(type(value) not in (int, float) or not math.isfinite(value)
                        for value in point)):
                raise ValueError("Finite " + label + " route point required")
            _bearing(point, [point[0] + 1, point[1]])
        if (polygon.covers(Point(route[0])) or
                not polygon.contains(Point(route[2])) or
                polygon.covers(Point(route[-1]))):
            raise ValueError(label + " route must enter and leave same crossing")
    left = _angle(_bearing(old_ego[0], old_ego[1]),
                  _bearing(old_ego[-2], old_ego[-1]))
    straight = _angle(_bearing(straight_ego_route[0], straight_ego_route[1]),
                      _bearing(straight_ego_route[-2], straight_ego_route[-1]))
    opposing = abs(_angle(_bearing(old_ego[0], old_ego[1]),
                           _bearing(old_routes["other"][0], old_routes["other"][1])))
    if not 45 <= left <= 135 or abs(straight) > 30 or abs(opposing - 180) > 20:
        raise ValueError("Left/straight controlled route geometry differs")
    comparator = copy.deepcopy(left_site)
    comparator["routes"]["ego"] = copy.deepcopy(straight_ego_route)
    if any(comparator[key] != left_site[key] for key in FIXED_SITE_FIELDS):
        raise ValueError("Controlled site field changed")
    return {"site": comparator, "baseline_site": copy.deepcopy(left_site),
            "straight_route_source": route_source,
            "left_deflection_deg": left, "straight_deflection_deg": straight,
            "approach_separation_deg": opposing,
            "physical_or_legal_acceptance_claimed": False}


def compare_sites(left_site, candidate_site, route_source):
    """Reject any undeclared site, opposing route or approach change."""
    source = verify_route_source(route_source)
    expected = straight_site(left_site, source["route_xy_m"], route_source)["site"]
    if candidate_site != expected:
        raise ValueError("Straight comparator changes a fixed site field or route")
    return {"fixed_fields": list(FIXED_SITE_FIELDS),
            "deliberate_difference": "ego exit route: left to straight",
            "straight_route_source_sha256": route_source["sha256"],
            "physical_or_legal_acceptance_claimed": False}


@contextmanager
def construct_straight_pair(world, blueprints, transforms, plan):
    """Spawn the same two approach lanes after checking the straight plan."""
    compare_sites(plan["baseline_site"], plan["site"],
                  plan["straight_route_source"])
    site = plan["site"]
    if set(blueprints) != set(ROLES) or set(transforms) != set(ROLES):
        raise ValueError("Both reviewed Native blueprints and transforms required")
    lanes = site["expected_approach_lanes"]
    if not isinstance(lanes, dict) or set(lanes) != set(ROLES) or lanes["ego"] == lanes["other"]:
        raise ValueError("Two distinct same-site approach lanes required")
    actors = {}
    try:
        for role in ROLES:
            actor = world.try_spawn_actor(blueprints[role], transforms[role])
            if actor is None:
                raise ValueError("Native actor spawn failed: " + role)
            actors[role] = actor
        world.tick()
        for role, actor in actors.items():
            waypoint = world.get_map().get_waypoint(actor.get_location(), project_to_road=False)
            if waypoint is None or [waypoint.road_id, waypoint.lane_id] != lanes[role]:
                raise ValueError("Native actor outside same-site approach lane: " + role)
            yaw = float(actor.get_transform().rotation.yaw)
            route = site["routes"][role]
            if not math.isfinite(yaw) or abs(_angle(_bearing(route[0], route[1]), yaw)) > 20:
                raise ValueError("Native actor faces away from sourced approach: " + role)
        yield actors
    finally:
        for actor in reversed(list(actors.values())):
            actor.destroy()


def command_straight_pair(carla, actors, plan, progress, frame_index,
                          release_frames, target_speeds_mps, lookahead_m=5.0):
    """Issue two route commands using the unchanged candidate timing controls."""
    compare_sites(plan["baseline_site"], plan["site"],
                  plan["straight_route_source"])
    if (set(actors) != set(ROLES) or set(progress) != set(ROLES) or
            set(release_frames) != set(ROLES) or
            set(target_speeds_mps) != set(ROLES) or
            type(frame_index) is not int or frame_index < 0 or
            any(type(release_frames[r]) is not int or release_frames[r] < 1 for r in ROLES) or
            any(type(target_speeds_mps[r]) not in (int, float) or
                not math.isfinite(target_speeds_mps[r]) or target_speeds_mps[r] <= 0
                for r in ROLES)):
        raise ValueError("Complete paired straight candidate controls required")
    decisions = {}
    for role in ROLES:
        pose = actors[role].get_transform()
        steer, next_index = steering_command(
            float(pose.location.x), float(pose.location.y), float(pose.rotation.yaw),
            plan["site"]["routes"][role], progress[role], lookahead_m)
        decisions[role] = {"steer": steer, "next_index": next_index,
                           "release_allowed": frame_index >= release_frames[role]}
    for role in ROLES:
        decision = decisions[role]
        decision["applied_control"] = apply_speed_control(
            carla, actors[role], float(target_speeds_mps[role]),
            not decision["release_allowed"], decision["steer"])
        progress[role] = decision["next_index"]
    return {"frame_index": frame_index, "decisions": decisions,
            "physical_or_legal_acceptance_claimed": False}


def run_straight_pair(world, carla, plan, blueprints, transforms,
                      release_frames, target_speeds_mps, frames,
                      collect_camera_frames, write_source, lookahead_m=5.0,
                      camera_factory=None):
    """Capture both original actor sources and four joined cameras each tick.

    The caller owns video encoding, frame-map writing and Core acquisition.
    It must persist the supplied source record without replacing Native values.
    """
    if (type(frames) is not int or not 2 <= frames <= 1100 or
            not callable(collect_camera_frames) or not callable(write_source)):
        raise ValueError("Bounded capture and source callbacks required")
    progress = {"ego": 1, "other": 1}
    first_frame = last_frame = None
    with construct_straight_pair(world, blueprints, transforms, plan) as actors:
        with ExitStack() as stack:
            if camera_factory is not None:
                collect_camera_frames = stack.enter_context(camera_factory(world, actors))
            for index in range(frames):
                decision = command_straight_pair(
                    carla, actors, plan, progress, index, release_frames,
                    target_speeds_mps, lookahead_m)
                native_frame = world.tick()
                if (type(native_frame) is not int or
                        (last_frame is not None and native_frame <= last_frame)):
                    raise ValueError("Increasing original Native frames required")
                cameras = collect_camera_frames(native_frame)
                if (not isinstance(cameras, dict) or set(cameras) != set(SIZES) or
                        any(type(frame) is not int or frame != native_frame
                            for frame in cameras.values())):
                    raise ValueError("All four cameras must join original Native frame")
                actors_source = {role: _actor(actor, world.get_map())
                                 for role, actor in actors.items()}
                if actors_source["ego"]["actor_id"] == actors_source["other"]["actor_id"]:
                    raise ValueError("Distinct original Native actor sources required")
                write_source({"native_frame": native_frame, "frame_index": index,
                              "maneuver": "ego_straight_other_straight",
                              "camera_source_frames": cameras,
                              "actor_sources": actors_source,
                              "applied_decisions": decision["decisions"],
                              "physical_or_legal_acceptance_claimed": False})
                if first_frame is None:
                    first_frame = native_frame
                last_frame = native_frame
    return {"frames_recorded": frames, "first_native_frame": first_frame,
            "last_native_frame": last_frame,
            "physical_or_legal_acceptance_claimed": False}


def _native_pose(carla, values):
    if (not isinstance(values, list) or len(values) != 6 or
            any(type(value) not in (int, float) or not math.isfinite(value)
                for value in values)):
        raise ValueError("Finite six-value Native pose required")
    return carla.Transform(carla.Location(x=values[0], y=values[1], z=values[2]),
                           carla.Rotation(yaw=values[3], pitch=values[4], roll=values[5]))


def _joined_camera_image(queue, native_frame):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError("Missing original straight camera frame") from error
        if image.frame == native_frame:
            return image
        if image.frame > native_frame:
            raise ValueError("Straight camera skipped original Native frame")
    raise ValueError("Straight camera frame join exhausted")


def capture_straight_media(output_dir, world, carla, plan, blueprints, transforms,
                           release_frames, target_speeds_mps, frames,
                           governed_lights, client, original_capture_factory=None,
                           lookahead_m=5.0):
    """Capture four lossless cameras and source rows for an exact reviewed site.

    A synthetic diagnostic review cannot enter this Native path. The caller
    provides a dedicated synchronous world; this function never starts CARLA.
    """
    root = Path(output_dir)
    if not root.is_dir() or not (root / "construction.json").is_file():
        raise ValueError("Existing exact straight construction required")
    config = json.loads((root / "config.json").read_text())
    construction = json.loads((root / "construction.json").read_text())
    control = config["candidate_plan"]["primary"]
    source = dict(config["straight_route_source"])
    source["path"] = str(root / source["path"])
    compare_sites(config["baseline_site"], config["site"], source)
    if (config.get("selected_case_id") != COMPARATOR_CASE or
            construction.get("case_id") != COMPARATOR_CASE or
            plan["site"] != config["site"] or
            not isinstance(control.get("transforms"), dict) or
            set(control["transforms"]) != set(ROLES) or
            any(control.get(key) != value for key, value in
                (("release_frames", release_frames), ("target_speeds_mps", target_speeds_mps),
                 ("frames", frames), ("lookahead_m", lookahead_m)))):
        raise ValueError("Straight capture differs from exact reviewed construction")
    from opposite_site_probe import verify_opposite_site_packet
    review = verify_opposite_site_packet(config, root)
    if review["diagnostic_only"]:
        raise ValueError("Diagnostic straight site cannot enter Native capture")
    live_map = world.get_map()
    if (live_map.name != config["site"]["native_map_name"] or
            hashlib.sha256(live_map.to_opendrive().encode()).hexdigest() != review["native_map_sha256"]):
        raise ValueError("Original Native map differs from reviewed straight site")
    site = plan["site"]
    if (not isinstance(governed_lights, dict) or set(governed_lights) != set(ROLES) or
            any(governed_lights[role].id != site["governed_signal_ids"][role]
                for role in ROLES)):
        raise ValueError("Two reviewed governed signal actors required")
    for role in ROLES:
        lane = site["expected_approach_lanes"][role]
        governed = {(int(w.road_id), int(w.lane_id)) for w in
                    governed_lights[role].get_affected_lane_waypoints()}
        if tuple(lane) not in governed:
            raise ValueError("Native signal does not govern straight approach: " + role)
        route = site["routes"][role]
        first = live_map.get_waypoint(
            carla.Location(x=route[0][0], y=route[0][1], z=0), project_to_road=False)
        middle = live_map.get_waypoint(
            carla.Location(x=route[2][0], y=route[2][1], z=0), project_to_road=False)
        if (first is None or [first.road_id, first.lane_id] != lane or
                middle is None or not middle.is_junction or
                middle.get_junction().id != site["native_junction_id"]):
            raise ValueError("Native straight route differs from reviewed approach: " + role)
    generated = {"capture", "road_geometry.json", "turn_route_context.json",
                 "stop_context.json", "signal_context.json", "body_history.jsonl",
                 "crossing_history.jsonl", "stop_history.jsonl", "signal_history.jsonl",
                 "video_frames.jsonl", "trace.jsonl", *(name + ".mkv" for name in SIZES)}
    if any((root / name).exists() for name in generated):
        raise ValueError("Retain prior straight acquisition; choose a fresh attempt")
    if original_capture_factory is None:
        from pipeline_capture import PipelineCapture
        original_capture_factory = PipelineCapture
    polygon = Polygon(site["crossing_polygon_xy_m"])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Sourced straight crossing polygon required")
    contexts = {
        "road_geometry.json": {"intersection_id": site["native_junction_id"],
            "intersection_polygon_xy_m": site["crossing_polygon_xy_m"],
            "site_review_sha256": review["packet_sha256"]},
        "turn_route_context.json": {"intersection_id": site["native_junction_id"],
            "routes": site["routes"], "site_review_sha256": review["packet_sha256"]},
        "stop_context.json": {"intersection_id": site["native_junction_id"],
            "selected_references": site["selected_stop_references"],
            "review_status": "candidate_only", "site_review_sha256": review["packet_sha256"]},
        "signal_context.json": {"intersection_id": site["native_junction_id"],
            "native_map_id": site["native_map_name"],
            "device_inventory_source": site["device_inventory_source"],
            "native_signal_id": site["governed_signal_ids"]["ego"],
            "other_native_signal_id": site["governed_signal_ids"]["other"],
            "governed_road_id": site["expected_approach_lanes"]["ego"][0],
            "governed_lane_id": site["expected_approach_lanes"]["ego"][1],
            "other_governed_road_id": site["expected_approach_lanes"]["other"][0],
            "other_governed_lane_id": site["expected_approach_lanes"]["other"][1],
            "review_status": "candidate_only", "site_review_sha256": review["packet_sha256"]}}
    for name, value in contexts.items():
        (root / name).write_text(json.dumps(value, allow_nan=False) + "\n")
    from worker_exchange.native_output import FrameMap
    with ExitStack() as stack:
        body = stack.enter_context((root / "body_history.jsonl").open("x", buffering=1))
        crossing = stack.enter_context((root / "crossing_history.jsonl").open("x", buffering=1))
        stop = stack.enter_context((root / "stop_history.jsonl").open("x", buffering=1))
        signal = stack.enter_context((root / "signal_history.jsonl").open("x", buffering=1))
        mapping = stack.enter_context(FrameMap(root / "video_frames.jsonl"))
        times = {}
        original_capture = None

        @contextmanager
        def cameras(active_world, actors):
            nonlocal original_capture
            original_capture = stack.enter_context(original_capture_factory(
                client, actors["ego"], root, COMPARATOR_CASE))
            camera_poses = {name: _native_pose(carla, values)
                            for name, values in site["cameras"].items()}
            sensors = stack.enter_context(source_cameras(active_world, actors["ego"], camera_poses))
            queues = {name: Queue() for name in SIZES}
            for name, sensor in sensors.items():
                sensor.listen(lambda image, camera_name=name: queues[camera_name].put(image))
            writers = {name: stack.enter_context(FFV1Writer(root / (name + ".mkv"), *size))
                       for name, size in SIZES.items()}
            def collect(native_frame):
                snapshot = active_world.get_snapshot()
                if snapshot.frame != native_frame:
                    raise ValueError("Straight snapshot differs from tick frame")
                time_s = float(snapshot.timestamp.elapsed_seconds)
                if not math.isfinite(time_s):
                    raise ValueError("Finite original straight time required")
                for name in SIZES:
                    writers[name].write(bytes(_joined_camera_image(queues[name], native_frame).raw_data))
                mapping.append(native_frame, time_s)
                times[native_frame] = time_s
                return {name: native_frame for name in SIZES}
            yield collect

        def write_source(record):
            native_frame = record["native_frame"]
            time_s = times.pop(native_frame)
            body.write(json.dumps(record, allow_nan=False) + "\n")
            if original_capture is not None:
                original_capture.capture(native_frame, time_s)
            actors = record["actor_sources"]
            crossing_row = {"frame": native_frame, "time_s": time_s,
                            "ego": actors["ego"], "other": actors["other"],
                            "ego_vertices_m": actors["ego"]["body_vertices_xy_m"]}
            crossing.write(json.dumps(crossing_row, allow_nan=False) + "\n")
            stop.write(json.dumps({"frame": native_frame, "time_s": time_s,
                "ego": _stop_state(actors["ego"], polygon),
                "other": _stop_state(actors["other"], polygon)}, allow_nan=False) + "\n")
            signal.write(json.dumps({"frame": native_frame, "time_s": time_s,
                "native_signal_id": site["governed_signal_ids"]["ego"],
                "state": _native_state(governed_lights["ego"]),
                "other_native_signal_id": site["governed_signal_ids"]["other"],
                "other_state": _native_state(governed_lights["other"])}, allow_nan=False) + "\n")
        try:
            return run_straight_pair(world, carla, plan, blueprints, transforms,
                release_frames, target_speeds_mps, frames, lambda _: {}, write_source,
                lookahead_m=lookahead_m, camera_factory=cameras)
        except ValueError as error:
            if str(error).startswith("Native actor spawn failed: "):
                (root / "spawn_attempt.json").write_text(json.dumps({
                    "format": "worker-c125751-straight-spawn-attempt-v1",
                    "selected_case_id": COMPARATOR_CASE,
                    "attempted_role": str(error).split(": ", 1)[1],
                    "approach_spawn_succeeded": False,
                    "site_review_sha256": review["packet_sha256"],
                    "physical_or_legal_acceptance_claimed": False}) + "\n")
            raise


def analyze_saved_straight(attempt, output):
    """Rebuild straight comparison measurements from retained original sources."""
    from shapely.geometry import MultiPoint
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Retain prior straight finalization; choose a fresh attempt")
    names = ("config.json", "straight-route-source.json", "opposite-site-review.json",
             "road_geometry.json", "turn_route_context.json",
             "body_history.jsonl", "crossing_history.jsonl", "signal_context.json",
             "signal_history.jsonl", "stop_context.json", "stop_history.jsonl",
             "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl",
             *(name + ".mkv" for name in SIZES))
    for name in names:
        if not (attempt / name).is_file():
            raise ValueError("Missing required straight source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    if (config.get("selected_case_id") != COMPARATOR_CASE or
            config.get("law_id") != "NRS-484B-250-2" or
            config.get("cell_id") != "C125751"):
        raise ValueError("Exact straight comparator config required")
    source = dict(config["straight_route_source"])
    source["path"] = str(attempt / source["path"])
    compare_sites(config["baseline_site"], config["site"], source)
    from opposite_site_probe import verify_opposite_site_packet
    review = verify_opposite_site_packet(config, attempt)
    packet = json.loads((attempt / "opposite-site-review.json").read_text())
    review_sources = tuple(item["path"] for item in packet["source_documents"].values())
    if "native_map_export" in packet:
        review_sources += (packet["native_map_export"]["path"],)
    names += review_sources
    road = json.loads((attempt / "road_geometry.json").read_text())
    route = json.loads((attempt / "turn_route_context.json").read_text())
    signal_context = json.loads((attempt / "signal_context.json").read_text())
    stop_context = json.loads((attempt / "stop_context.json").read_text())
    if (route.get("routes") != config["site"]["routes"] or
            road.get("intersection_id") != config["site"]["native_junction_id"] or
            route.get("intersection_id") != road["intersection_id"] or
            road.get("intersection_polygon_xy_m") != config["site"]["crossing_polygon_xy_m"]):
        raise ValueError("Saved straight site differs from sourced comparison plan")
    if any(context.get("site_review_sha256") != review["packet_sha256"]
           for context in (road, route, signal_context, stop_context)):
        raise ValueError("Saved straight context differs from reviewed site packet")
    if (signal_context.get("intersection_id") != road["intersection_id"] or
            signal_context.get("device_inventory_source") != config["site"]["device_inventory_source"] or
            signal_context.get("native_signal_id") != config["site"]["governed_signal_ids"]["ego"] or
            signal_context.get("other_native_signal_id") != config["site"]["governed_signal_ids"]["other"] or
            stop_context.get("intersection_id") != road["intersection_id"] or
            stop_context.get("selected_references") != config["site"]["selected_stop_references"]):
        raise ValueError("Saved straight signal or stop source differs from fixed site")
    def rows(name):
        return [json.loads(line) for line in (attempt / name).read_text().splitlines() if line.strip()]
    mapping, bodies, crossing, signals, stops, trace, evidence = (
        rows(name) for name in ("video_frames.jsonl", "body_history.jsonl",
            "crossing_history.jsonl", "signal_history.jsonl", "stop_history.jsonl",
            "trace.jsonl", "capture/evidence.jsonl"))
    if not (len(mapping) >= 2 and len(mapping) == len(bodies) == len(crossing) ==
            len(signals) == len(stops) == len(trace) == len(evidence)):
        raise ValueError("Complete original straight sources and camera history required")
    polygon = Polygon(road["intersection_polygon_xy_m"])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Valid saved crossing polygon required")
    first = {role: None for role in ROLES}
    previous = -1
    for index, (frame, body, crossed, signal, stop, motion, observed) in enumerate(
            zip(mapping, bodies, crossing, signals, stops, trace, evidence)):
        native = frame.get("carla_frame")
        when = frame.get("time_s")
        if (type(native) is not int or native <= previous or
                frame.get("video_frame") != index or
                body.get("native_frame") != native or body.get("frame_index") != index or
                body.get("maneuver") != "ego_straight_other_straight" or
                body.get("camera_source_frames") != {name: native for name in SIZES} or
                body.get("actor_sources") != {role: crossed.get(role) for role in ROLES} or
                any(row.get("frame") != native or row.get("time_s") != when
                    for row in (crossed, signal, stop, motion)) or
                observed.get("original_frame") != native or
                observed.get("recording_time_s") != when or
                signal.get("native_signal_id") != signal_context["native_signal_id"] or
                signal.get("other_native_signal_id") != signal_context["other_native_signal_id"] or
                any(not isinstance(stop.get(role), dict) or
                    stop[role].get("native_road_id") != crossed[role].get("native_road_id") or
                    stop[role].get("native_lane_id") != crossed[role].get("native_lane_id")
                    for role in ROLES)):
            raise ValueError("Original straight source/frame join failed")
        previous = native
        for role in ROLES:
            actor = crossed.get(role)
            vertices = actor.get("body_vertices_xy_m") if isinstance(actor, dict) else None
            if (not isinstance(vertices, list) or len(vertices) < 4 or
                    any(not isinstance(point, list) or len(point) != 2 or
                        any(type(value) not in (int, float) or not math.isfinite(value)
                            for value in point) for point in vertices)):
                raise ValueError("Finite original straight body vertices required: " + role)
            inside = MultiPoint(vertices).convex_hull.intersects(polygon)
            if index == 0 and inside:
                raise ValueError("Straight actor starts inside crossing: " + role)
            if first[role] is None and inside:
                first[role] = {"frame": native, "time_s": when}
    if not all(first.values()):
        raise ValueError("Both original straight body entries required")
    source_hashes = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                     for name in names}
    channels = attempt / "channels"
    channels.mkdir()
    for filename, source_rows in (("signal_state.jsonl", signals), ("stop_state.jsonl", stops)):
        with (channels / filename).open("x") as stream:
            for row in source_rows:
                stream.write(json.dumps({"time_s": row["time_s"], "value": row},
                                        allow_nan=False) + "\n")
    measurement = {"first_body_entry": first,
                   "ego_minus_other_entry_time_s": first["ego"]["time_s"] - first["other"]["time_s"],
                   "straight_route_source_sha256": source["sha256"],
                   "physical_or_legal_acceptance_claimed": False}
    (channels / "entry_context.json").write_text(json.dumps(
        {"entry_context": measurement}, indent=2, allow_nan=False) + "\n")
    result = {"case_id": COMPARATOR_CASE,
              "measured_values": measurement,
              "target_checks": [{"target": "opposing_straight_body_entries",
                  "requested": True, "measured": True,
                  "method": "original paired body/camera/source-route join",
                  "tolerance": 0, "matched": True,
                  "physical_cause_confirmed": False,
                  "cause_evidence": ["body_history.jsonl", "crossing_history.jsonl",
                                     "video_frames.jsonl", "turn_route_context.json"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved straight comparison sources measured; physical/legal review pending",
              "physical_failure_flags": ["official device and priority judgments unresolved"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in SIZES],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": [{"name": name, "unit": "structured record",
                  "reference": "channels/" + name + ext} for name, ext in
                  (("signal_state", ".jsonl"), ("stop_state", ".jsonl"),
                   ("entry_context", ".json"))],
              "source_evidence_hashes": source_hashes,
              "capture_evidence_sha256": source_hashes["capture/evidence.jsonl"],
              "realized_observables": {}}
    write_result(attempt, physical_result(attempt, result))
    output.write_text(json.dumps({"format": "worker-c125751-straight-saved-analysis-v1",
        "case_id": COMPARATOR_CASE, "measurements": measurement,
        "source_evidence_hashes": source_hashes,
        "physical_acceptance_claimed": False, "legal_acceptance_claimed": False},
        indent=2, allow_nan=False) + "\n")
    return measurement
