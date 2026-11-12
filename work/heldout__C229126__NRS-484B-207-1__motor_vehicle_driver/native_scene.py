"""CARLA-lazy exact overtaking actor placement for the C229126 cell."""

from overtake_route import select_overtake_route


def build_scene(world, *, blueprint_id='vehicle.tesla.model3',
                other_index=8, route_steps=70):
    if not 4 <= other_index < route_steps:
        raise ValueError('Overtaken actor must start ahead on selected route')
    route = select_overtake_route(world.get_map(), steps=route_steps)
    blueprints = world.get_blueprint_library()
    blueprint = blueprints.find(blueprint_id)
    if blueprint is None:
        raise ValueError('Native overtaking vehicle blueprint unavailable')
    actors = []
    try:
        other = world.try_spawn_actor(blueprint, route['right'][other_index].transform)
        if other is None:
            raise ValueError('Native overtaken actor spawn failed')
        actors.append(other)
        ego = world.try_spawn_actor(blueprint, route['right'][0].transform)
        if ego is None:
            raise ValueError('Native overtaking subject spawn failed')
        actors.append(ego)
        if ego.id == other.id:
            raise ValueError('Native overtaking actor identity collided')
        return {'route': route, 'ego': ego, 'other': other, 'actors': actors,
                'spawn_indices': {'ego': 0, 'other': other_index}}
    except BaseException:
        for actor in reversed(actors):
            actor.destroy()
        raise


def destroy_scene(scene):
    for actor in reversed(scene['actors']):
        actor.destroy()
