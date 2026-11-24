"""Spawn a visible person candidate for the officer exception capture.

Blueprint identity and position are construction facts. Police authority and
actual traffic control require original-camera review after capture.
"""

import json
import math
from pathlib import Path


BLUEPRINT_ID = "walker.pedestrian.0001"
POSITION_XYZ_M = (6.0, -6.0, 0.25)


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


def write_candidate_packet(output, actor):
    output = Path(output)
    if type(actor.id) is not int or actor.type_id != BLUEPRINT_ID:
        raise ValueError("Missing source-identified officer candidate")
    actual = actor.get_location()
    packet = {"format": "worker-officer-candidate-construction",
              "actor_id": actor.id, "blueprint_id": actor.type_id,
              "position_xyz_m": [actual.x, actual.y, actual.z],
              "police_authority_judgment": "unresolved",
              "traffic_control_observed": "pending original-camera review"}
    path = output / "officer-candidate.json"
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    return path
