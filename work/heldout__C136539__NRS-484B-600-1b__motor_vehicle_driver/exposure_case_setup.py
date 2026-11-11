"""Exact engineering settings for the six C136539 exposure comparisons.

These settings select physical scenes. They do not define legal endangerment.
"""

from math import hypot


PREFIX = 'heldout__C136539__NRS-484B-600-1b__motor_vehicle_driver__'
CASES = {
    'slow_person_exposure': (2.0, 'pedestrian', 0.4),
    'moderate_person_exposure': (5.0, 'pedestrian', 0.4),
    'fast_person_exposure': (8.0, 'pedestrian', 0.4),
    'clearance_reference': (5.0, 'pedestrian', 2.0),
    'property_near': (5.0, 'property', 0.4),
    'property_far': (5.0, 'property', 2.0),
}


def case_settings(config):
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'NRS-484B-600-1b', 'C136539', 'motor_vehicle_driver'):
        raise ValueError('Exposure case identity differs')
    case_id = config.get('selected_case_id', '')
    if not case_id.startswith(PREFIX):
        raise ValueError('Unknown exact exposure case')
    suffix = case_id[len(PREFIX):]
    if suffix not in CASES:
        raise ValueError('Unknown exact exposure case')
    speed, kind, lateral = CASES[suffix]
    if (config.get('rate_hz'), config.get('frames'), config.get('duration_s')) != (20, 160, 8):
        raise ValueError('Exposure cases require 160 frames at 20 Hz over 8 s')
    if config.get('requested_speed_mps') != speed or config.get('exposed_kind') != kind or config.get('outside_edge_m') != lateral:
        raise ValueError('Exposure case engineering setting differs')
    if config.get('construction_probe_only') is not True:
        raise ValueError('Construction case may not masquerade as delivery')
    return {'case_id': case_id, 'speed_mps': speed, 'exposed_kind': kind,
            'outside_edge_m': lateral}


def exposed_transform_point(route, *, outside_edge_m, waypoint_index=8):
    if len(route) <= waypoint_index or outside_edge_m < 0:
        raise ValueError('Exposure route or lateral placement invalid')
    waypoint = route[waypoint_index]
    forward = waypoint.transform.get_forward_vector()
    norm = hypot(forward.x, forward.y)
    if norm < 1e-6:
        raise ValueError('Exposure route tangent undefined')
    point = waypoint.transform.location
    offset = waypoint.lane_width / 2 + outside_edge_m
    return [point.x - forward.y / norm * offset,
            point.y + forward.x / norm * offset, point.z]


def spawn_exposed(world, carla, route, settings):
    """Spawn an actual participant or fixed property body at the requested verge."""
    point = exposed_transform_point(route, outside_edge_m=settings['outside_edge_m'])
    kind = settings['exposed_kind']
    blueprint_id = ('walker.pedestrian.0001' if kind == 'pedestrian'
                    else 'vehicle.tesla.model3')
    blueprint = world.get_blueprint_library().find(blueprint_id)
    transform = carla.Transform(carla.Location(*point), route[8].transform.rotation)
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise ValueError('Native exposed ' + kind + ' spawn failed')
    if kind == 'property':
        actor.set_simulate_physics(False)
    return actor
