"""Spawn two source-specified Native vehicles for moving-traffic backing."""
from traffic_geometry import validate


def construct(world, packet, transforms):
    reviewed = validate(packet)
    if set(transforms) != {'vehicle', 'traffic'} or any(transforms[key] is None for key in transforms):
        raise ValueError('two reviewed original vehicle transforms required')
    if world.get_map().name != packet['map_name']:
        raise ValueError('original Native moving-traffic map identity differs')
    library = world.get_blueprint_library()
    blueprints = {key: library.find(packet[name]) for key, name in
                  (('vehicle', 'vehicle_blueprint_id'), ('traffic', 'traffic_blueprint_id'))}
    owned = []
    try:
        for key in ('vehicle', 'traffic'):
            actor = world.try_spawn_actor(blueprints[key], transforms[key])
            if actor is None:
                raise ValueError('Native moving-traffic actor spawn failed: ' + key)
            owned.append(actor)
            if actor.type_id != blueprints[key].id:
                raise ValueError('Native moving-traffic actor blueprint readback differs: ' + key)
        return {'vehicle': owned[0], 'traffic': owned[1],
                'map_sha256': reviewed['map_sha256'], 'junction_id': reviewed['junction_id'],
                'cleanup': lambda: [actor.destroy() for actor in reversed(owned)]}
    except BaseException:
        for actor in reversed(owned):
            actor.destroy()
        raise
