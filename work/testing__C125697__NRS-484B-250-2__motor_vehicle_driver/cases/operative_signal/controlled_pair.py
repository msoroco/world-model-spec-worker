"""Join reviewed median routes with all-entrance Native Off setup."""
from contextlib import contextmanager

from native_pair import construct_pair, plan_pair
from signal_control import find_entrance_lights, request_operative


@contextmanager
def construct_operational_pair(world, site, transforms, other_blueprint, traffic_light_state, side):
    world_map = world.get_map()
    if world_map.name != site.get('native_map_name'):
        raise ValueError('Native map differs from reviewed median site')
    plan = plan_pair(world_map, site, transforms, side)
    inventory = site.get('entrance_road_lanes')
    if not isinstance(inventory, list) or len(inventory) < 2:
        raise ValueError('All Native entrance lanes must be inventoried')
    lanes = [tuple(row) for row in inventory]
    for role in ('ego', 'other'):
        approach = plan['approaches'][role]
        if (approach['road_id'], approach['lane_id']) not in lanes:
            raise ValueError(role + ' approach omitted from signal inventory')
    if (lanes[0] != (plan['approaches']['ego']['road_id'], plan['approaches']['ego']['lane_id']) or
            lanes[1] != (plan['approaches']['other']['road_id'], plan['approaches']['other']['lane_id'])):
        raise ValueError('Operative head inventory must map ego then other')
    lights = find_entrance_lights(world, lanes)
    with request_operative(world, lights, traffic_light_state):
        with construct_pair(world, site, transforms, other_blueprint, side) as (plan, other):
            yield plan, other, lights
