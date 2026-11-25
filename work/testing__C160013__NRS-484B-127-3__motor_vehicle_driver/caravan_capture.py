"""CARLA-lazy original-frame capture core for a reviewed Native caravan site.

The caller owns world restoration, actor/camera lifetime, and source sealing.
This module never treats an intended merge as observed occupancy or legal safety.
"""
import hashlib
import json
import math
from pathlib import Path
from queue import Empty, Queue

from caravan_control import apply, command
from caravan_entry import plan_entry

CAMERAS = ("overview", "caravan_gap", "entrant_approach", "driver_reference")
SOURCE_KEYS = ("business_district_source", "caravan_membership_source",
               "route_source", "lane_source")


def validate_site(packet, root, native_map_id):
    """Require a reviewed Native site and bind its four original context files."""
    if packet.get("site_review_status") != "reviewed_native_site":
        raise ValueError("Reviewed Native caravan site required")
    for key in ("reviewer", "district_review_basis", "caravan_review_basis",
                "highway_review_basis", "camera_review_basis"):
        value = packet.get(key)
        if (not isinstance(value, str) or not value.strip() or
                any(word in value.lower() for word in ("synthetic", "diagnostic", "fixture"))):
            raise ValueError("Original Native site review required: " + key)
    if packet.get("native_map_id") in (None, "", "FixtureMap", "TownX"):
        raise ValueError("Original Native map identity required")
    if packet.get("native_map_id") != native_map_id:
        raise ValueError("Native map differs from reviewed caravan site")
    if packet.get("outside_business_district") is not True or packet.get("caravan_or_motorcade") is not True:
        raise ValueError("District and caravan activation unresolved")
    if not packet.get("highway_id") or not packet.get("road_id"):
        raise ValueError("Reviewed highway and road IDs required")
    if not isinstance(packet.get("road_forward_xy"), list) or len(packet["road_forward_xy"]) != 2:
        raise ValueError("Reviewed highway direction required")
    if any(type(value) not in (int, float) or not math.isfinite(value)
           for value in packet["road_forward_xy"]):
        raise ValueError("Finite highway direction required")
    if math.hypot(*packet["road_forward_xy"]) <= 0:
        raise ValueError("Nonzero highway direction required")
    if not isinstance(packet.get("roadway_polygon_xy_m"), list) or len(packet["roadway_polygon_xy_m"]) < 4:
        raise ValueError("Reviewed highway polygon required")
    hashes = {}
    root = Path(root).resolve()
    for key in SOURCE_KEYS:
        ref = packet.get(key)
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not isinstance(ref.get("sha256"), str):
            raise ValueError("Original context source required: " + key)
        relative = Path(ref["path"])
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise ValueError("Unsafe context source: " + key)
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Missing original context source: " + key)
        data = path.read_bytes()
        if not data or len(data) > 2 * 1024 * 1024:
            raise ValueError("Invalid original context source size: " + key)
        data.decode("utf-8")
        digest = hashlib.sha256(data).hexdigest()
        if digest != ref["sha256"]:
            raise ValueError("Changed original context source: " + key)
        hashes[key] = digest
    return hashes


def body(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = [[float(vertex.x), float(vertex.y)] for vertex in vertices]
    if len(points) < 4 or any(not all(math.isfinite(value) for value in point) for point in points):
        raise ValueError("Incomplete original Native vehicle body")
    return points


def state(actor):
    transform = actor.get_transform()
    velocity = actor.get_velocity()
    points = body(actor)
    yaw = float(transform.rotation.yaw)
    speed = math.hypot(float(velocity.x), float(velocity.y))
    if not math.isfinite(yaw) or not math.isfinite(speed):
        raise ValueError("Nonfinite original Native vehicle state")
    blueprint_id = getattr(actor, "type_id", None)
    if not isinstance(blueprint_id, str) or not blueprint_id:
        raise ValueError("Original Native vehicle type identity required")
    return {"actor_id": int(actor.id), "blueprint_id": blueprint_id,
            "body_vertices_xy_m": points,
            "position_xy": [float(transform.location.x), float(transform.location.y)],
            "yaw_deg": yaw, "speed_mps": speed}


def _image(queue, frame):
    for _ in range(6):
        try:
            image = queue.get(timeout=10)
        except Empty as error:
            raise ValueError("Original source camera frame missing") from error
        if image.frame == frame:
            return image
        if image.frame > frame:
            raise ValueError("Source camera skipped Native frame")
    raise ValueError("Original source camera frame join failed")


def capture_frames(world, carla, caravan, entrant, sensors, encoders, mapping,
                   history, pipeline_capture, packet, *, outcome, frames=900):
    """Drive four vehicles and join all four cameras to each original Native tick."""
    if len(caravan) < 3 or len({actor.id for actor in caravan + [entrant]}) != len(caravan) + 1:
        raise ValueError("Three distinct caravan vehicles and distinct entrant required")
    if set(sensors) != set(CAMERAS) or set(encoders) != set(CAMERAS):
        raise ValueError("Four original source cameras and encoders required")
    if type(frames) is not int or frames < 2:
        raise ValueError("Original frame count required")
    if outcome not in ("occupy", "stop_before"):
        raise ValueError("Exact caravan comparison outcome required")
    queues = {name: Queue() for name in CAMERAS}
    for name, sensor in sensors.items():
        sensor.listen(lambda image, camera=name: queues[camera].put(image))
    plan = None
    last_frame = None
    last_time = None
    count = 0
    for index in range(frames):
        members_before = [state(actor) for actor in caravan]
        entrant_before = state(entrant)
        if plan is None:
            plan = plan_entry(packet, members_before, entrant_before["body_vertices_xy_m"],
                              gap_index=packet["selected_gap_index"], outcome=outcome)
        for member in members_before:
            actor = next(actor for actor in caravan if actor.id == member["actor_id"])
            target = [member["position_xy"][0] + packet["road_forward_xy"][0] * 25,
                      member["position_xy"][1] + packet["road_forward_xy"][1] * 25]
            values = command(member["position_xy"], member["yaw_deg"], member["speed_mps"],
                             target, target_speed_mps=packet["target_speed_mps"])
            apply(actor, carla, values)
        waypoints = plan["waypoints_xy_m"]
        target = waypoints[0]
        if outcome == "occupy" and len(waypoints) > 1:
            if math.dist(entrant_before["position_xy"], target) < 1.0:
                target = waypoints[1]
        values = command(entrant_before["position_xy"], entrant_before["yaw_deg"],
                         entrant_before["speed_mps"], target,
                         target_speed_mps=packet["target_speed_mps"])
        apply(entrant, carla, values)
        world.tick()
        snapshot = world.get_snapshot()
        frame = int(snapshot.frame)
        time_s = float(snapshot.timestamp.elapsed_seconds)
        if last_frame is not None and frame != last_frame + 1:
            raise ValueError("Original Native frame cadence broken")
        if not math.isfinite(time_s) or (last_time is not None and abs(time_s - last_time - .05) > 1e-4):
            raise ValueError("Original Native 20 Hz time cadence broken")
        last_frame = frame
        last_time = time_s
        for name in CAMERAS:
            encoders[name].write(bytes(_image(queues[name], frame).raw_data))
        pipeline_capture.capture(frame, time_s)
        mapping.append(frame, time_s)
        members_after = [state(actor) for actor in caravan]
        entrant_after = state(entrant)
        selected = {member["actor_id"]: member for member in members_after}
        rear = selected[plan["rear_actor_id"]]
        front = selected[plan["front_actor_id"]]
        waypoint = world.get_map().get_waypoint(entrant.get_location(), project_to_road=False)
        if waypoint is None or type(waypoint.lane_id) is not int:
            raise ValueError("Original Native entrant lane readback missing")
        history.write(json.dumps({"frame": frame, "time_s": time_s,
                                  "road_id": packet["road_id"],
                                  "caravan_members": [{key: member[key] for key in ("actor_id", "blueprint_id", "body_vertices_xy_m")}
                                                      for member in members_after],
                                  "entering_vehicle": {key: entrant_after[key] for key in
                                                       ("actor_id", "blueprint_id", "body_vertices_xy_m")},
                                  "participants": {
                                      "rear": {"actor_id": rear["actor_id"], "body_vertices_m": rear["body_vertices_xy_m"]},
                                      "subject": {"actor_id": front["actor_id"], "body_vertices_m": front["body_vertices_xy_m"]},
                                      "entrant": {"actor_id": entrant_after["actor_id"],
                                                  "body_vertices_m": entrant_after["body_vertices_xy_m"],
                                                  "lane_id": int(waypoint.lane_id)}}},
                                 separators=(",", ":")) + "\n")
        count = index + 1
    return {"frames": count, "first_frame": last_frame - count + 1,
            "last_frame": last_frame, "plan": plan,
            "physical_acceptance_claimed": False,
            "without_danger_judgment": "unresolved"}
