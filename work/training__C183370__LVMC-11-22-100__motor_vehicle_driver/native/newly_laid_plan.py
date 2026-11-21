"""Survey and live-map contract for the newly laid pavement alternative.

The plan fixes the warning person and routes. The source reference is a review
requirement; neither a survey label nor a live waypoint proves surface age.
"""
import math
from math import hypot

from shapely.geometry import LineString, Point, Polygon

ASSIGNMENT = 'training__C183370__LVMC-11-22-100__motor_vehicle_driver'
ROUTES = ('newly_laid_crossing', 'newly_laid_avoidance')


def _xy(value, name):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(n) not in (int, float) or not math.isfinite(n)
                for n in value)):
        raise ValueError(name + ' needs finite XY coordinates')
    return value


def _route(value, name):
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError(name + ' needs at least two surveyed points')
    return LineString([_xy(point, name) for point in value])


def validate(survey, live_map_name):
    if not isinstance(survey, dict):
        raise ValueError('Newly laid survey must be an object')
    required = {'cell_id', 'map_name', 'road_id', 'laid_polygon_xy_m',
                'route_over_xy_m', 'route_avoid_xy_m', 'frames',
                'anchor_z_m', 'ego_blueprint', 'weather_profile',
                'warning_person_actor_id', 'warning_person_type_id',
                'warning_person_xy_m', 'surface_condition_source',
                'warning_act_source', 'operator_activity_source'}
    if not required <= set(survey):
        raise ValueError('Missing newly laid source/survey facts: ' +
                         ', '.join(sorted(required - set(survey))))
    if survey['cell_id'] != 'C183370' or survey['map_name'] != live_map_name:
        raise ValueError('Newly laid plan must use the fixed live C183370 cell')
    if (type(survey['road_id']) is not int or
            type(survey['warning_person_actor_id']) is not int or
            type(survey['frames']) is not int or survey['frames'] < 600):
        raise ValueError('Original road/person identity and 30-second capture required')
    if (type(survey['anchor_z_m']) not in (int, float) or
            not math.isfinite(survey['anchor_z_m'])):
        raise ValueError('Survey elevation must be finite')
    if (not isinstance(survey['warning_person_type_id'], str) or
            not survey['warning_person_type_id'].startswith('walker.pedestrian.')):
        raise ValueError('Warning person needs an original pedestrian type')
    for key in ('ego_blueprint', 'weather_profile',
                'surface_condition_source', 'warning_act_source',
                'operator_activity_source'):
        if not isinstance(survey[key], str) or not survey[key].strip():
            raise ValueError('Missing source-bound newly laid context: ' + key)
    polygon_points = survey['laid_polygon_xy_m']
    if not isinstance(polygon_points, list) or len(polygon_points) < 3:
        raise ValueError('Newly laid surface needs a surveyed polygon')
    polygon = Polygon([_xy(point, 'Laid polygon') for point in polygon_points])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Laid polygon is invalid')
    over = _route(survey['route_over_xy_m'], 'Crossing route')
    avoid = _route(survey['route_avoid_xy_m'], 'Avoidance route')
    if over.length <= 0 or avoid.length <= 0 or not over.crosses(polygon) or avoid.intersects(polygon):
        raise ValueError('Routes must isolate newly laid surface contact')
    if (Point(over.coords[0]).distance(Point(avoid.coords[0])) > .5 or
            Point(over.coords[-1]).distance(Point(avoid.coords[-1])) > .5):
        raise ValueError('Controlled routes need common surveyed endpoints')
    warning_xy = _xy(survey['warning_person_xy_m'], 'Warning person')
    if Point(warning_xy).distance(polygon) > 15:
        raise ValueError('Warning person must be near the surface')
    return {
        'cell_id': 'C183370', 'map_name': live_map_name,
        'road_id': survey['road_id'], 'laid_polygon_xy_m': polygon_points,
        'frames': survey['frames'], 'capture_rate_hz': 20,
        'anchor_z_m': survey['anchor_z_m'],
        'ego_blueprint': survey['ego_blueprint'],
        'weather_profile': survey['weather_profile'],
        'warning_person_actor_id': survey['warning_person_actor_id'],
        'warning_person_type_id': survey['warning_person_type_id'],
        'warning_person_xy_m': warning_xy,
        'source_references': {key: survey[key] for key in
                              ('surface_condition_source', 'warning_act_source',
                               'operator_activity_source')},
        'cases': {
            ROUTES[0]: {'case_id': ASSIGNMENT + '__' + ROUTES[0],
                        'route_xy_m': survey['route_over_xy_m'],
                        'requested_pavement_crossing': True},
            ROUTES[1]: {'case_id': ASSIGNMENT + '__' + ROUTES[1],
                        'route_xy_m': survey['route_avoid_xy_m'],
                        'requested_pavement_crossing': False},
        },
        'newly_laid_status_verified': False,
        'warning_act_verified': False,
        'operator_exception_verified': False,
        'physical_completion_claimed': False,
    }


def bind(survey, world, carla):
    """Join a source survey to live waypoints and the fixed warning actor."""
    mapping = world.get_map()
    plan = validate(survey, mapping.name)
    z = plan['anchor_z_m']
    points = plan['laid_polygon_xy_m']
    center = [sum(point[i] for point in points) / len(points) for i in (0, 1)]
    pavement = mapping.get_waypoint(
        carla.Location(x=center[0], y=center[1], z=z),
        project_to_road=False, lane_type=carla.LaneType.Any)
    if pavement is None or pavement.road_id != plan['road_id']:
        raise ValueError('Live surface road differs from survey')
    routes = {}
    for name, case in plan['cases'].items():
        rows = []
        for x, y in case['route_xy_m']:
            waypoint = mapping.get_waypoint(
                carla.Location(x=x, y=y, z=z),
                project_to_road=False, lane_type=carla.LaneType.Any)
            if waypoint is None or waypoint.lane_type not in (
                    carla.LaneType.Driving, carla.LaneType.Shoulder):
                raise ValueError('Newly laid route leaves live drivable pavement: ' + name)
            rows.append({'road_id': waypoint.road_id,
                         'lane_id': waypoint.lane_id,
                         'lane_type': str(waypoint.lane_type)})
        routes[name] = rows
    person = world.get_actors().find(plan['warning_person_actor_id'])
    if person is None or person.type_id != plan['warning_person_type_id']:
        raise ValueError('Live warning person differs from source survey')
    observed = person.get_transform().location
    surveyed = plan['warning_person_xy_m']
    if hypot(observed.x - surveyed[0], observed.y - surveyed[1]) > .5:
        raise ValueError('Live warning person position differs from survey')
    return {'plan': plan, 'source_kind': 'live_carla_map_and_actor_readback',
            'pavement_road_id': pavement.road_id,
            'pavement_lane_id': pavement.lane_id,
            'route_waypoints': routes,
            'warning_person_actor_id': person.id,
            'warning_person_type_id': person.type_id,
            'warning_person_xyz_m': [observed.x, observed.y, observed.z],
            'newly_laid_status_verified': False,
            'warning_act_verified': False,
            'operator_exception_verified': False,
            'physical_completion_claimed': False}
