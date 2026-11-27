"""Prospective CARLA bicycle rider rig with original skeletal readback.

The rig moves a walker with the selected bicycle and requests a hand pose.
Its output is an acquisition source, never evidence of visible or valid signaling.
"""
from __future__ import annotations

from math import cos, radians, sin


BLUEPRINT = "vehicle.bh.crossbike"
BONES = {
    "right_horizontal": ("crl_shoulder__R", "crl_arm__R", "crl_foreArm__R", "crl_hand__R"),
    "left_upward": ("crl_shoulder__L", "crl_arm__L", "crl_foreArm__L", "crl_hand__L"),
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def spawn_rider(world, carla, bicycle, walker_blueprint_id):
    """Spawn a separately identified rider; do not infer mounted identity."""
    _require(bicycle.type_id == BLUEPRINT, "Selected bicycle blueprint required")
    _require(walker_blueprint_id.startswith("walker.pedestrian."), "Walker skeleton required")
    blueprint = world.get_blueprint_library().find(walker_blueprint_id)
    _require(blueprint is not None, "Rider blueprint unavailable")
    pose = bicycle.get_transform()
    rider = world.try_spawn_actor(blueprint, carla.Transform(
        carla.Location(x=pose.location.x, y=pose.location.y, z=pose.location.z + 0.85),
        carla.Rotation(yaw=pose.rotation.yaw)))
    _require(rider is not None and getattr(rider, "id", None) != bicycle.id,
             "Distinct rider actor spawn failed")
    return rider


def _bone_request(carla, method):
    _require(method in BONES or method == "none", "Unknown hand-signal method")
    if method == "none":
        return []
    side = "R" if method == "right_horizontal" else "L"
    # Parent-relative pose request. Original bone readback and pixels determine
    # whether the intended horizontal/upward shape was actually achieved.
    rotations = ((0, 0, -45 if side == "R" else 45),
                 (0, 0, -55 if side == "R" else 55),
                 (0, 0, -35 if side == "R" else 35),
                 (0, 90, 0))
    return [(name, carla.Transform(rotation=carla.Rotation(
        pitch=pitch, yaw=yaw, roll=roll)))
            for name, (pitch, yaw, roll) in zip(BONES[method], rotations)]


def request_rider(carla, bicycle, rider, *, method, mount_height_m=0.85):
    """Submit pose before a Native tick; return only the requested control."""
    _require(bicycle.type_id == BLUEPRINT, "Selected bicycle blueprint required")
    _require(getattr(rider, "id", None) != bicycle.id, "Rider and bicycle IDs must differ")
    _require(0.5 <= mount_height_m <= 1.3, "Rider mount height outside authored range")
    pose = bicycle.get_transform()
    yaw = radians(pose.rotation.yaw)
    rider_pose = carla.Transform(carla.Location(
        x=pose.location.x - 0.12 * cos(yaw),
        y=pose.location.y - 0.12 * sin(yaw),
        z=pose.location.z + mount_height_m), carla.Rotation(yaw=pose.rotation.yaw))
    rider.set_transform(rider_pose)
    requested = _bone_request(carla, method)
    if requested:
        _require(callable(getattr(rider, "set_bones", None)) and
                 hasattr(carla, "WalkerBoneControlIn"),
                 "Native articulated rider control unavailable")
        rider.set_bones(carla.WalkerBoneControlIn(requested))
        _require(callable(getattr(rider, "show_pose", None)),
                 "Native rider pose blending unavailable")
        rider.show_pose()
    else:
        _require(callable(getattr(rider, "hide_pose", None)),
                 "Native rider neutral pose unavailable")
        rider.hide_pose()
    return {"requested_method": method,
            "requested_bones": [name for name, _ in requested]}


def sample_rider(bicycle, rider, *, request, frame):
    """Read original bicycle and articulated bone geometry after a Native tick."""
    _require(bicycle.type_id == BLUEPRINT, "Selected bicycle blueprint required")
    _require(getattr(rider, "id", None) != bicycle.id, "Rider and bicycle IDs must differ")
    _require(type(frame) is int and frame >= 0, "Native frame required")
    pose = bicycle.get_transform()
    bounding_box = getattr(bicycle, "bounding_box", None)
    _require(bounding_box is not None and callable(getattr(bounding_box, "get_world_vertices", None)),
             "Original bicycle body readback unavailable")
    vertices = bounding_box.get_world_vertices(pose)
    _require(len(vertices) >= 4, "Original bicycle body vertices missing")
    body = [[float(vertex.x), float(vertex.y), float(vertex.z)] for vertex in vertices]
    _require(callable(getattr(rider, "get_bones", None)),
             "Original rider bone readback unavailable")
    raw = rider.get_bones().bone_transforms
    names = {entry.name if hasattr(entry, "name") else entry[0] for entry in raw}
    _require(set(BONES["right_horizontal"] + BONES["left_upward"]) <= names,
             "Original rider arm bones absent")
    readback = {}
    for entry in raw:
        name = entry.name if hasattr(entry, "name") else entry[0]
        if name not in BONES["right_horizontal"] + BONES["left_upward"]:
            continue
        world_transform = getattr(entry, "world", None)
        world_location = getattr(world_transform, "location", None)
        _require(world_location is not None and all(
            hasattr(world_location, coordinate) for coordinate in ("x", "y", "z")),
            "Original rider bone world position unavailable")
        readback[name] = [float(world_location.x), float(world_location.y),
                          float(world_location.z)]
    rider_pose = rider.get_transform()
    return {
        "frame": frame, "rider_actor_id": rider.id,
        "bicycle_actor_id": bicycle.id, "bicycle_blueprint": bicycle.type_id,
        "requested_method": request["requested_method"],
        "requested_bones": request["requested_bones"],
        "readback_bones": sorted(names), "bone_world_xyz_m": readback,
        "bicycle_yaw_deg": pose.rotation.yaw,
        "bicycle_center_xyz_m": [pose.location.x, pose.location.y, pose.location.z],
        "bicycle_body_vertices_xyz_m": body,
        "rider_world_xyz_m": [rider_pose.location.x, rider_pose.location.y,
                              rider_pose.location.z],
        "physical_mount_verified": False, "arm_pixels_verified": False,
    }


def step_rider(carla, bicycle, rider, *, method, frame, mount_height_m=0.85):
    """CPU convenience wrapper; live capture separates request and post-tick sample."""
    request = request_rider(carla, bicycle, rider, method=method,
                            mount_height_m=mount_height_m)
    return sample_rider(bicycle, rider, request=request, frame=frame)
