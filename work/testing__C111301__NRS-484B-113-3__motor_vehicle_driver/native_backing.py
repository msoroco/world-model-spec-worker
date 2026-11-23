"""Lazy Native actor setup from a validated original map packet.

Callers supply CARLA transforms and blueprint library; no CARLA import occurs on
CPU. Spawn failures clean up actors owned by this construction.
"""
from backing_geometry import validate


def construct(world, packet, transforms):
    reviewed = validate(packet)
    if set(transforms) != {"vehicle", "pedestrian"} or any(transforms[k] is None for k in transforms):
        raise ValueError("source-bound Native vehicle and pedestrian transforms required")
    native_map = world.get_map()
    if native_map.name != packet["map_name"]:
        raise ValueError("Native map identity differs from original packet")
    library = world.get_blueprint_library()
    vehicle_bp = library.find(reviewed["vehicle_blueprint_id"])
    pedestrian_bp = library.find(reviewed["pedestrian_blueprint_id"])
    owned = []
    try:
        for blueprint, key in ((vehicle_bp,"vehicle"),(pedestrian_bp,"pedestrian")):
            actor = world.try_spawn_actor(blueprint, transforms[key])
            if actor is None:
                raise ValueError("Native actor spawn failed: " + key)
            owned.append(actor)
            if actor.type_id != blueprint.id:
                raise ValueError("Native actor blueprint readback differs: " + key)
        return {"vehicle": owned[0], "pedestrian": owned[1],
                "map_sha256": reviewed["map_sha256"], "junction_id": reviewed["junction_id"],
                "cleanup": lambda: [actor.destroy() for actor in reversed(owned)]}
    except Exception:
        for actor in reversed(owned):
            actor.destroy()
        raise
