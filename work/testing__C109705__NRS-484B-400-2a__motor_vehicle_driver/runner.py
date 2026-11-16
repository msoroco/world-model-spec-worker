"""Inspect both intersecting Native roads for opposite-direction driving lanes.

Signed lane IDs are an engineering preflight, not proof of legal highway status
or the exact physical centerline; original map/camera review remains required.
"""

import hashlib
import json
import math
import subprocess
from contextlib import ExitStack, contextmanager
from pathlib import Path
from queue import Empty, Queue

from shapely.geometry import LineString, MultiPoint, Point, Polygon

CAMERA_PROFILE = {
    "overview": (1920, 1080),
    "approach": (1280, 720),
    "reference_corner": (1280, 720),
    "driver_reference": (1280, 720),
}


def verify_two_directional_roads(world, approach_road_id, outgoing_road_id,
                                 *, waypoint_spacing_m=2.0):
    if approach_road_id==outgoing_road_id:
        raise ValueError("Two intersecting road identities required")
    waypoints=world.get_map().generate_waypoints(waypoint_spacing_m)
    lanes={approach_road_id:set(),outgoing_road_id:set()}
    for waypoint in waypoints:
        if waypoint.road_id in lanes and str(waypoint.lane_type).lower().endswith("driving"):
            lanes[waypoint.road_id].add(waypoint.lane_id)
    for road_id,ids in lanes.items():
        if not any(i>0 for i in ids) or not any(i<0 for i in ids):
            raise ValueError("Opposite-direction Native driving lanes missing on road "+str(road_id))
    return {"approach_road_id":approach_road_id,"outgoing_road_id":outgoing_road_id,
            "native_lane_ids":{str(key):sorted(value) for key,value in lanes.items()},
            "legal_two_directional_status":"unresolved pending source review"}


def _geometry_points(value, label, minimum):
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError("Missing " + label)
    points = []
    for point in value:
        if (not isinstance(point, list) or len(point) != 2 or
                any(type(number) not in (int, float) or
                    not math.isfinite(number) for number in point)):
            raise ValueError("Invalid " + label)
        points.append(tuple(float(number) for number in point))
    return points


def _review_source(root, reference, label):
    if not isinstance(reference, dict) or not reference.get("path") or not reference.get("sha256"):
        raise ValueError("Missing " + label + " source")
    relative = Path(reference["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe " + label + " source path")
    source = Path(root) / relative
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != reference["sha256"]:
        raise ValueError("Stale or missing " + label + " source")
    return {"path": reference["path"], "sha256": reference["sha256"]}


def validate_approach_site(world, packet, root):
    """Check a reviewed two-way approach packet against the loaded Native map.

    This binds map geometry and review documents; it does not settle legal road
    status or prove the vehicle's eventual physical position in a recording.
    """
    if not isinstance(packet, dict):
        raise ValueError("Approach site packet required")
    mapping = world.get_map()
    if packet.get("native_map_id") != mapping.name or packet.get("intersection_id") is None:
        raise ValueError("Native map or intersection identity differs")
    approach = packet.get("approach_road_id")
    outgoing = packet.get("outgoing_road_id")
    lane = packet.get("approach_lane_id")
    if any(type(value) is not int for value in (approach, outgoing, lane)) or lane == 0:
        raise ValueError("Exact Native approach and outgoing lane identities required")
    inventory = verify_two_directional_roads(world, approach, outgoing)
    if lane not in inventory["native_lane_ids"][str(approach)]:
        raise ValueError("Selected approach lane absent from Native inventory")
    if packet.get("centerline_kind") not in ("marked", "imaginary"):
        raise ValueError("Marked or imaginary centerline kind required")
    center = LineString(_geometry_points(packet.get("centerline_xy_m"), "centerline", 2))
    right = Polygon(_geometry_points(packet.get("right_half_polygon_xy_m"), "right half", 3))
    junction = Polygon(_geometry_points(packet.get("junction_polygon_xy_m"), "junction", 3))
    route = LineString(_geometry_points(packet.get("approach_route_xy_m"), "approach route", 2))
    if (center.length <= 0 or not right.is_valid or right.area <= 0 or
            not junction.is_valid or junction.area <= 0 or route.length <= 0 or
            not center.intersects(right.boundary) or not right.intersects(junction) or
            not right.covers(route) or not route.intersects(junction)):
        raise ValueError("Approach centerline, right half, route or junction geometry differs")
    names = ("approach_road_source", "outgoing_road_source", "centerline_source",
             "right_half_source", "junction_source", "route_source")
    sources = {name: _review_source(root, packet.get(name), name) for name in names}
    if len({source["path"] for source in sources.values()}) != len(sources):
        raise ValueError("Distinct review source documents required")
    if not packet.get("reviewer") or not packet.get("review_basis"):
        raise ValueError("Explicit site review basis required")
    return {"format": "worker-c109705-approach-site-review",
            "native_map_id": mapping.name, "intersection_id": packet["intersection_id"],
            "approach_road_id": approach, "approach_lane_id": lane,
            "outgoing_road_id": outgoing, "centerline_kind": packet["centerline_kind"],
            "native_lane_inventory": inventory, "sources": sources,
            "physical_approach_position": "unverified", "legal_two_directional_status": "unresolved"}


def plan_left_turn(world, packet, root):
    """Construct a left turn following a source-bound right-half approach."""
    review = validate_approach_site(world, packet, root)
    approach = _geometry_points(packet["approach_route_xy_m"], "approach route", 2)
    route = _geometry_points(packet.get("left_turn_route_xy_m"), "left turn route", 4)
    junction = Polygon(_geometry_points(packet["junction_polygon_xy_m"], "junction", 3))
    if route[:len(approach)] != approach:
        raise ValueError("Turn route does not preserve reviewed approach")
    if any(math.dist(a, b) < 0.1 for a, b in zip(route, route[1:])):
        raise ValueError("Duplicate turn route points")
    approach_vector = (approach[-1][0]-approach[-2][0],
                       approach[-1][1]-approach[-2][1])
    exit_vector = (route[-1][0]-route[-2][0], route[-1][1]-route[-2][1])
    if (math.hypot(*approach_vector) < 0.1 or math.hypot(*exit_vector) < 0.1 or
            approach_vector[0]*exit_vector[1]-approach_vector[1]*exit_vector[0] <= 0):
        raise ValueError("Route must make a left turn")
    if not junction.intersects(LineString(route[len(approach)-1:])):
        raise ValueError("Turn route misses reviewed junction")
    if junction.covers(Point(route[-1])):
        raise ValueError("Turn route must exit reviewed junction")
    return {"route_xy_m": [list(point) for point in route],
            "source_review": review, "physical_completion_claimed": False}


def four_camera_plan(packet, route_xy_m):
    """Camera placement intent; Native capture must confirm actual visibility."""
    route = _geometry_points(route_xy_m, "left turn route", 4)
    z = packet.get("start_z_m")
    if type(z) not in (int, float) or not math.isfinite(z):
        raise ValueError("Finite Native spawn height required")
    start, corner, departure = route[0], route[len(route)//2], route[-1]
    yaw = math.degrees(math.atan2(route[1][1]-start[1], route[1][0]-start[0]))
    cameras = [
        {"name": "overview", "mount": "world", "position_xyz_m": [corner[0]+12, corner[1]+12, z+30], "yaw_deg": yaw-135, "pitch_deg": -75},
        {"name": "approach", "mount": "world", "position_xyz_m": [start[0]-6, start[1]+4, z+7], "yaw_deg": yaw, "pitch_deg": -20},
        {"name": "reference_corner", "mount": "world", "position_xyz_m": [departure[0]+8, corner[1]+5, z+8], "yaw_deg": yaw+120, "pitch_deg": -35},
        {"name": "driver_reference", "mount": "ego_vehicle", "position_xyz_m": [1, 0, 1.65], "yaw_deg": 0, "pitch_deg": -5},
    ]
    for camera in cameras:
        camera["width"], camera["height"] = CAMERA_PROFILE[camera["name"]]
        camera["fov_deg"] = 75
        camera["visibility_verified"] = False
    return cameras


class RouteFollower:
    """Bounded, CARLA-independent steering and speed controller."""
    def __init__(self, route_xy_m, *, target_speed_mps=4.0, reach_m=2.0):
        self.route = _geometry_points(route_xy_m, "route", 2)
        if (type(target_speed_mps) not in (int, float) or
                not math.isfinite(target_speed_mps) or not 0 < target_speed_mps <= 8):
            raise ValueError("Bounded turn speed required")
        if type(reach_m) not in (int, float) or not math.isfinite(reach_m) or reach_m <= 0:
            raise ValueError("Positive waypoint reach required")
        if any(math.dist(a, b) < 0.1 for a, b in zip(self.route, self.route[1:])):
            raise ValueError("Duplicate route points")
        self.speed, self.reach, self.index = float(target_speed_mps), float(reach_m), 1

    def step(self, position_xy_m, forward_xy, speed_mps):
        position, forward = _geometry_points([list(position_xy_m), list(forward_xy)], "vehicle state", 2)
        px, py = position
        if (type(speed_mps) not in (int, float) or
                not math.isfinite(speed_mps) or speed_mps < 0):
            raise ValueError("Invalid observed speed")
        norm = math.hypot(*forward)
        if norm < 0.1:
            raise ValueError("Zero vehicle forward vector")
        fx, fy = forward[0]/norm, forward[1]/norm
        while self.index < len(self.route)-1 and math.dist((px, py), self.route[self.index]) <= self.reach:
            self.index += 1
        tx, ty = self.route[self.index]
        vx, vy = tx-px, ty-py
        distance = math.hypot(vx, vy)
        if self.index == len(self.route)-1 and distance <= self.reach:
            return {"throttle": 0.0, "brake": 1.0, "steer": 0.0,
                    "route_complete": True, "target_index": self.index}
        angle = math.atan2(fx*vy-fy*vx, fx*vx+fy*vy)
        error = self.speed-float(speed_mps)
        return {"throttle": max(0.0, min(0.45, 0.12*error)),
                "brake": max(0.0, min(0.6, -0.2*error)),
                "steer": max(-1.0, min(1.0, angle/math.radians(40))),
                "route_complete": False, "target_index": self.index}


def check_bundle(root):
    """Offline bundle preflight; does not contact CARLA or claim a real site."""
    root = Path(root)
    config = json.loads((root/"config.json").read_text())
    packet = json.loads((root/"site_packet.json").read_text())
    assignment = "testing__C109705__NRS-484B-400-2a__motor_vehicle_driver"
    case = assignment + "__source_verified_near_centerline"
    if (config.get("law_id"), config.get("cell_id"), config.get("actor"),
            config.get("selected_case_id")) != ("NRS-484B-400-2a", "C109705",
                                              "motor_vehicle_driver", case):
        raise ValueError("Exact first selected case identity required")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("Pinned capture rate and duration required")
    cameras = config.get("cameras")
    if (not isinstance(cameras, list) or
            [row.get("name") for row in cameras] != list(CAMERA_PROFILE)):
        raise ValueError("Four ordered source cameras required")
    if any((row.get("width"), row.get("height")) != CAMERA_PROFILE[row["name"]]
           for row in cameras):
        raise ValueError("Pinned source camera dimensions required")
    if (type(config.get("requested_speed_mps")) not in (int, float) or
            not 0 < config["requested_speed_mps"] <= 8 or
            not isinstance(config.get("required_atoms"), list)):
        raise ValueError("Bounded speed and observation contract required")
    if packet.get("centerline_kind") != "marked":
        raise ValueError("First selected case requires marked centerline")
    if (type(packet.get("connector_road_id")) is not int or
            len({packet.get("approach_road_id"), packet.get("connector_road_id"),
                 packet.get("outgoing_road_id")}) != 3 or
            not isinstance(packet.get("vehicle_blueprint_id"), str)):
        raise ValueError("Distinct Native turn road identities and vehicle blueprint required")
    direction = packet.get("departure_direction_xy")
    if (not isinstance(direction, list) or len(direction) != 2 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in direction) or
            math.hypot(*direction) <= 0):
        raise ValueError("Finite departure roadway direction required")
    for name in ("approach_road_source", "outgoing_road_source", "centerline_source",
                 "right_half_source", "junction_source", "route_source"):
        _review_source(root, packet.get(name), name)
    _geometry_points(packet.get("left_turn_route_xy_m"), "left turn route", 4)
    return {"case_id": case, "cpu_check_passed": True,
            "native_site_verified": False, "simulation_started": False}


class FFV1Writer:
    """Write one original BGRA camera stream without lossy re-encoding."""
    def __init__(self, path, width, height, fps=20):
        self.path = Path(path)
        if self.path.exists() or width <= 0 or height <= 0 or fps != 20:
            raise ValueError("Fresh source path and pinned video profile required")
        self.width, self.height, self.frames, self.exit_code = width, height, 0, None
        self.process = subprocess.Popen([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-n",
            "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
            "-framerate", "20", "-i", "pipe:0", "-an", "-c:v", "ffv1",
            "-level", "3", "-pix_fmt", "bgr0", str(self.path)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def write(self, bgra):
        if not isinstance(bgra, bytes) or len(bgra) != self.width*self.height*4:
            raise ValueError("Original BGRA frame size differs")
        if self.process.poll() is not None:
            raise ValueError("Source encoder exited before frame write")
        self.process.stdin.write(bgra)
        self.frames += 1

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        self.exit_code = self.process.wait(timeout=60)
        error = self.process.stderr.read().decode(errors="replace")
        self.process.stderr.close()
        if self.exit_code != 0 or self.frames == 0 or not self.path.is_file():
            raise ValueError("FFV1 source encoder failed: " + error[-1000:])

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


@contextmanager
def source_cameras(world, ego, carla, plan):
    """Create and clean up all four pinned Native RGB cameras."""
    if [row.get("name") for row in plan] != list(CAMERA_PROFILE):
        raise ValueError("Four ordered original cameras required")
    sensors = {}
    try:
        for row in plan:
            name = row["name"]
            if (row.get("width"), row.get("height")) != CAMERA_PROFILE[name]:
                raise ValueError("Pinned source camera dimensions required")
            blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", row["width"]),
                               ("image_size_y", row["height"]),
                               ("fov", row["fov_deg"]), ("sensor_tick", .05)):
                blueprint.set_attribute(key, str(value))
            x, y, z = row["position_xyz_m"]
            pose = carla.Transform(carla.Location(x=x, y=y, z=z),
                                   carla.Rotation(yaw=row["yaw_deg"], pitch=row["pitch_deg"]))
            kwargs = {"attach_to": ego} if row["mount"] == "ego_vehicle" else {}
            sensor = world.spawn_actor(blueprint, pose, **kwargs)
            if sensor is None:
                raise ValueError("Native camera spawn failed: " + name)
            sensors[name] = sensor
        yield sensors
    finally:
        for sensor in reversed(list(sensors.values())):
            sensor.stop()
            sensor.destroy()


def _camera_frame(queue, native_frame):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError("Original camera frame missing") from error
        if image.frame == native_frame:
            return image
        if image.frame > native_frame:
            raise ValueError("Original camera skipped Native frame")
    raise ValueError("Original camera frame join failed")


def capture(output_dir, host="127.0.0.1", port=2000):
    """Prospective Native run; no CARLA import or server contact in --check."""
    import carla
    from pipeline_capture import PipelineCapture
    from worker_exchange.native_output import FrameMap, seal_capture
    from worker_exchange.world_restore import snapshot as snapshot_world, restore

    output = Path(output_dir).resolve()
    if not output.is_dir() or not (output/"construction.json").is_file():
        raise ValueError("Materialize the exact construction before Native capture")
    config = json.loads((output/"config.json").read_text())
    packet = json.loads((output/"site_packet.json").read_text())
    check_bundle(output)
    client = carla.Client(host, port)
    client.set_timeout(30)
    saved = snapshot_world(client)
    world = client.get_world()
    actor = helper = None
    encoders = {}
    frames = 0
    error = None
    try:
        prepared = plan_left_turn(world, packet, output)
        route = prepared["route_xy_m"]
        junction = Polygon(_geometry_points(packet["junction_polygon_xy_m"], "junction", 3))
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        world.apply_settings(settings)
        heading = math.degrees(math.atan2(route[1][1]-route[0][1],
                                          route[1][0]-route[0][0]))
        spawn = carla.Location(x=route[0][0], y=route[0][1], z=packet["start_z_m"])
        waypoint = world.get_map().get_waypoint(spawn, project_to_road=False)
        if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (
                packet["approach_road_id"], packet["approach_lane_id"]):
            raise ValueError("Native approach spawn road/lane differs")
        blueprint = world.get_blueprint_library().find(packet["vehicle_blueprint_id"])
        actor = world.try_spawn_actor(blueprint, carla.Transform(
            spawn, carla.Rotation(yaw=heading)))
        if actor is None:
            raise ValueError("Native left-turn vehicle spawn failed")
        follower = RouteFollower(route, target_speed_mps=config["requested_speed_mps"])
        plan = four_camera_plan(packet, route)
        if any((a["name"], a["width"], a["height"], a["fov_deg"]) !=
               (b["name"], b["width"], b["height"], b["fov_deg"])
               for a, b in zip(plan, config["cameras"])):
            raise ValueError("Camera plan differs from exact config")
        geometry = {"intersection_xy_m": packet["junction_polygon_xy_m"],
                    "approach_road_id": packet["approach_road_id"],
                    "connector_road_id": packet["connector_road_id"],
                    "departure_road_id": packet["outgoing_road_id"],
                    "departure_direction_xy": packet["departure_direction_xy"],
                    "two_way": True, "site_source_review": prepared["source_review"]}
        (output/"road_geometry.json").write_text(json.dumps(geometry, indent=2)+"\n")
        first_entry = None
        with source_cameras(world, actor, carla, plan) as sensors:
            queues = {name: Queue() for name in CAMERA_PROFILE}
            for name, sensor in sensors.items():
                sensor.listen(lambda image, name=name: queues[name].put(image))
            with ExitStack() as stack:
                for name, (width, height) in CAMERA_PROFILE.items():
                    encoders[name] = stack.enter_context(FFV1Writer(
                        output/(name+".mkv"), width, height))
                mapping = stack.enter_context(FrameMap(output/"video_frames.jsonl"))
                body_file = stack.enter_context((output/"body_history.jsonl").open("x", buffering=1))
                approach_file = stack.enter_context((output/"approach_history.jsonl").open("x", buffering=1))
                helper = PipelineCapture(client, actor, output, config["selected_case_id"],
                                         required_observations=config["required_atoms"])
                try:
                    for _ in range(config["duration_s"]*config["rate_hz"]):
                        pose, velocity = actor.get_transform(), actor.get_velocity()
                        forward = [math.cos(math.radians(pose.rotation.yaw)),
                                   math.sin(math.radians(pose.rotation.yaw))]
                        control = follower.step([pose.location.x, pose.location.y], forward,
                                                math.hypot(velocity.x, velocity.y))
                        actor.apply_control(carla.VehicleControl(
                            throttle=control["throttle"], brake=control["brake"],
                            steer=control["steer"]))
                        world.tick()
                        snapshot = world.get_snapshot()
                        body = [[float(v.x), float(v.y), float(v.z)] for v in
                                actor.bounding_box.get_world_vertices(actor.get_transform())]
                        if len(body) < 4:
                            raise ValueError("Complete Native vehicle body missing")
                        waypoint = world.get_map().get_waypoint(
                            actor.get_transform().location, project_to_road=False)
                        if waypoint is None:
                            raise ValueError("Original Native road identity missing")
                        inside = MultiPoint([v[:2] for v in body]).convex_hull.intersects(junction)
                        frame, time_s = int(snapshot.frame), float(snapshot.timestamp.elapsed_seconds)
                        for name in CAMERA_PROFILE:
                            encoders[name].write(bytes(_camera_frame(queues[name], frame).raw_data))
                        helper.capture(frame, time_s)
                        mapping.append(frame, time_s)
                        row = {"frame": frame, "time_s": time_s, "road_id": int(waypoint.road_id),
                               "lane_id": int(waypoint.lane_id), "body_vertices_m": body}
                        body_file.write(json.dumps(row, separators=(",", ":"))+"\n")
                        if inside and first_entry is None:
                            first_entry = frame
                        if first_entry is None:
                            approach = {"frame": frame, "time_s": time_s,
                                        "road_id": row["road_id"], "lane_id": row["lane_id"],
                                        "body_in_intersection": False,
                                        "ego_body_vertices_xy_m": [v[:2] for v in body]}
                            approach_file.write(json.dumps(approach, separators=(",", ":"))+"\n")
                        frames += 1
                finally:
                    helper.close()
                    helper = None
        context = {"native_map_id": packet["native_map_id"],
                   "intersection_id": packet["intersection_id"],
                   "approach_road_id": packet["approach_road_id"],
                   "approach_lane_id": packet["approach_lane_id"],
                   "outgoing_road_id": packet["outgoing_road_id"],
                   "opposing_lane_source": "original Native waypoint inventory",
                   "centerline_source": packet["centerline_source"]["path"],
                   "right_half_source": packet["right_half_source"]["path"],
                   "junction_source": packet["junction_source"]["path"],
                   "left_turn_route_source": packet["route_source"]["path"],
                   "both_highways_two_directional": True, "intended_turn": "left",
                   "centerline_kind": packet["centerline_kind"],
                   "centerline_xy_m": packet["centerline_xy_m"],
                   "right_half_polygon_xy_m": packet["right_half_polygon_xy_m"],
                   "first_entry_frame": first_entry,
                   "site_source_review": prepared["source_review"]}
        (output/"road_context.json").write_text(json.dumps(context, indent=2)+"\n")
    except BaseException as caught:
        error = caught
        (output/"native-run-status.json").write_text(json.dumps({
            "errors": [type(caught).__name__+": "+str(caught)],
            "frames": frames, "capture_sealed": False}, indent=2)+"\n")
        raise
    finally:
        cleanup = []
        if helper is not None:
            try:
                helper.close(confirmed=False)
            except BaseException as caught:
                cleanup.append(str(caught))
        if actor is not None:
            try:
                actor.destroy()
            except BaseException as caught:
                cleanup.append(str(caught))
        restoration = restore(client, saved)
        if error is None and not cleanup:
            seal_capture(output, frames=frames, restoration=restoration, errors=[],
                         encoder_exit_codes={name: encoder.exit_code for name, encoder in encoders.items()},
                         context={"site_source_review": prepared["source_review"],
                                  "physical_acceptance_claimed": False})
        if error is None and cleanup:
            raise ValueError("Native cleanup failed: "+"; ".join(cleanup))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check_bundle(Path(__file__).parent)))
    elif args.output_dir:
        capture(args.output_dir, args.host, args.port)
    else:
        raise ValueError("--output-dir required for Native capture")
