"""Spawn a visible person candidate for the officer exception capture.

Blueprint identity and position are construction facts. Police authority and
actual traffic control require original-camera review after capture.
"""

import json
import math
from pathlib import Path


BLUEPRINT_ID = "walker.pedestrian.0030"
POSITION_XYZ_M = (6.0, -6.0, 0.25)
GESTURE_BONE = "crl_shoulder__R"
GESTURE_PITCH_OFFSET_DEG = -70.0


def spawn_candidate(world, *, location_factory, rotation_factory, transform_factory):
    library = world.get_blueprint_library()
    blueprint = library.find(BLUEPRINT_ID)
    if blueprint is None or blueprint.id != BLUEPRINT_ID:
        raise ValueError("Officer candidate pedestrian blueprint unavailable")
    location = location_factory(x=POSITION_XYZ_M[0], y=POSITION_XYZ_M[1],
                                z=POSITION_XYZ_M[2])
    rotation = rotation_factory(yaw=180.0)
    actor = world.try_spawn_actor(blueprint, transform_factory(location, rotation))
    if actor is None:
        raise ValueError("Officer candidate Native spawn failed")
    try:
        actual = actor.get_location()
        displacement = math.dist((actual.x, actual.y), POSITION_XYZ_M[:2])
        if (actor.type_id != BLUEPRINT_ID or type(actor.id) is not int
                or displacement > 2.0):
            raise ValueError("Officer candidate Native readback differs")
    except BaseException:
        actor.destroy()
        raise
    return actor


def apply_direction_pose(actor, *, transform_factory, rotation_factory,
                         bone_control_factory):
    """Command a right-arm direction pose and record the native bone readback.

    The command is a construction fact. Whether it is visible as traffic
    direction at the entry is decided from original camera frames.
    """
    before = {row[0]: row[3] for row in actor.get_bones().bone_transforms}
    if GESTURE_BONE not in before:
        raise ValueError("Officer direction shoulder bone unavailable")
    relative = before[GESTURE_BONE]
    baseline = relative.rotation
    wanted = rotation_factory(pitch=baseline.pitch + GESTURE_PITCH_OFFSET_DEG,
                              yaw=baseline.yaw, roll=baseline.roll)
    actor.get_pose_from_animation()
    actor.set_bones(bone_control_factory([
        (GESTURE_BONE, transform_factory(relative.location, wanted))]))
    actor.show_pose()
    return {"bone": GESTURE_BONE,
            "pitch_offset_deg": GESTURE_PITCH_OFFSET_DEG,
            "commanded_relative_rotation_deg":
                {"pitch": wanted.pitch, "yaw": wanted.yaw, "roll": wanted.roll}}


def read_direction_pose(actor, command):
    after = {row[0]: row[3] for row in actor.get_bones().bone_transforms}
    if GESTURE_BONE not in after:
        raise ValueError("Officer direction bone readback unavailable")
    rotation = after[GESTURE_BONE].rotation
    wanted = command["commanded_relative_rotation_deg"]
    actual = {"pitch": rotation.pitch, "yaw": rotation.yaw, "roll": rotation.roll}
    if any(abs(actual[axis] - wanted[axis]) > 2.0 for axis in wanted):
        raise ValueError("Officer direction pose Native readback differs")
    return actual


def write_candidate_packet(output, actor, *, pose_command, pose_readback):
    output = Path(output)
    if type(actor.id) is not int or actor.type_id != BLUEPRINT_ID:
        raise ValueError("Missing source-identified officer candidate")
    actual = actor.get_location()
    packet = {"format": "worker-officer-candidate-construction",
              "actor_id": actor.id, "blueprint_id": actor.type_id,
              "position_xyz_m": [actual.x, actual.y, actual.z],
              "direction_pose_command": pose_command,
              "direction_pose_readback_deg": pose_readback,
              "police_authority_judgment": "unresolved",
              "traffic_control_observed": "pending original-camera review"}
    path = output / "officer-candidate.json"
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    return path
