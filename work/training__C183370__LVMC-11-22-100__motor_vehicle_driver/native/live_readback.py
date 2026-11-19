"""Bind the warning-person draft geometry to a live CARLA map and actor.

No warning gesture, newly repaired surface, or completed route is inferred.
Those need original camera and actor sources after capture.
"""
from math import hypot, isfinite

from scene_plan import validate


def bind(survey, world, carla):
    mapping = world.get_map()
    plan = validate(survey, mapping.name)
    if (type(survey.get('anchor_z_m')) not in (int, float) or
            not isfinite(survey['anchor_z_m'])):
        raise ValueError('Survey needs original route elevation')
    elevation = survey['anchor_z_m']
    polygon = survey['repair_polygon_xy_m']
    x = sum(p[0] for p in polygon) / len(polygon)
    y = sum(p[1] for p in polygon) / len(polygon)
    location = carla.Location(x=x, y=y, z=elevation)
    pavement = mapping.get_waypoint(location, project_to_road=False,
                                    lane_type=carla.LaneType.Any)
    if pavement is None or pavement.road_id != survey['road_id']:
        raise ValueError('Live repaired-pavement road differs from survey')
    route_readbacks = {}
    for case, item in plan['cases'].items():
        rows = []
        for x, y in item['route_xy_m']:
            waypoint = mapping.get_waypoint(
                carla.Location(x=x, y=y, z=elevation),
                project_to_road=False, lane_type=carla.LaneType.Any)
            if waypoint is None:
                raise ValueError('Survey route has no live-map waypoint: '+case)
            if waypoint.lane_type not in (carla.LaneType.Driving,
                                          carla.LaneType.Shoulder):
                raise ValueError('Survey route leaves drivable pavement: '+case)
            rows.append({'road_id': waypoint.road_id,
                         'lane_id': waypoint.lane_id,
                         'lane_type': str(waypoint.lane_type)})
        route_readbacks[case] = rows
    person = world.get_actors().find(survey['warning_person_actor_id'])
    if person is None or not person.type_id.startswith('walker.pedestrian.'):
        raise ValueError('Survey warning person absent from live world')
    observed = person.get_transform().location
    surveyed = survey['warning_person_xy_m']
    if hypot(observed.x-surveyed[0], observed.y-surveyed[1]) > 0.5:
        raise ValueError('Live warning person position differs from survey')
    return {'plan': plan,
            'source_kind': 'live_carla_map_and_actor_readback',
            'pavement_road_id': pavement.road_id,
            'pavement_lane_id': pavement.lane_id,
            'route_waypoints': route_readbacks,
            'warning_person_actor_id': person.id,
            'warning_person_type_id': person.type_id,
            'warning_person_xyz_m': [observed.x, observed.y, observed.z],
            'warning_act_observed': False,
            'physical_completion_claimed': False}
