"""Read the C201084 draft construction against a live CARLA map and sign actor.

The returned geometry is a prepared request, not evidence that a vehicle
stopped, the sign face was legible, or the City designated the fire lane.
"""
from math import hypot

from fire_lane_survey import build, require


def inspect(world, carla, survey):
    mapping = world.get_map()
    require(mapping.name == survey.get('map_name') and
            not mapping.name.startswith('pending_'),
            'Live CARLA map differs from the surveyed map')
    actor_id = survey.get('posted_sign_actor_id')
    require(type(actor_id) is int, 'Posted sign needs a live actor ID')
    actor = world.get_actors().find(actor_id)
    require(actor is not None and
            isinstance(getattr(actor, 'type_id', None), str) and
            actor.type_id.startswith('static.prop.'),
            'Posted sign actor missing or wrong type')
    observed = actor.get_transform().location
    requested = survey.get('posted_sign_xy_m')
    require(isinstance(requested, list) and len(requested) == 2 and
            hypot(observed.x-requested[0], observed.y-requested[1]) <= 0.5,
            'Posted sign actor moved from surveyed location')
    anchor_z = survey.get('anchor_z_m')
    require(type(anchor_z) in (int, float),
            'Live survey needs an anchor elevation')

    def probe(xy):
        location = carla.Location(x=xy[0], y=xy[1], z=anchor_z)
        waypoint = mapping.get_waypoint(location, project_to_road=True,
                                        lane_type=carla.LaneType.Driving)
        if waypoint is None:
            raise ValueError('No live driving access near destination stop')
        mapped = waypoint.transform.location
        planar_offset = hypot(mapped.x-xy[0], mapped.y-xy[1])
        return {'map_name': mapping.name, 'road_id': waypoint.road_id,
                'lane_id': waypoint.lane_id,
                'drivable_access': planar_offset <= 5,
                'projected_road_offset_m': planar_offset,
                'source_kind': 'original_carla_map_readback'}

    plan = build(survey, probe)
    plan['sign_readback'] = {'actor_id': actor.id, 'type_id': actor.type_id,
                             'position_xy_m': [observed.x, observed.y],
                             'source_kind': 'original_carla_actor_readback'}
    return plan
