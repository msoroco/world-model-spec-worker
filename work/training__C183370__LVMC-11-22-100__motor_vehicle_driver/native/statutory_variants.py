"""Survey and live-readback contract for C183370's remaining statute routes.

This is a construction component. Actor identity and geometry are mechanical;
pixels, warning content, repair history and employee status need original review.
"""
import math
from math import hypot

from shapely.geometry import LineString, Point, Polygon


CONTROL_KINDS = ('barrier', 'warning_sign', 'highway_closed_sign',
                 'warning_person', 'employee_exception')
SIGN_KINDS = ('warning_sign', 'highway_closed_sign')


def _point(value, label):
    if not isinstance(value, list) or len(value) != 2 or any(
            type(n) not in (int, float) or not math.isfinite(n) for n in value):
        raise ValueError(label + ' needs finite XY coordinates')
    return value


def _route(value, label):
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError(label + ' needs two or more points')
    return LineString([_point(p, label) for p in value])


def validate(survey, live_map_name):
    """Validate a measured crossing/avoidance pair without deciding the law."""
    if not isinstance(survey, dict):
        raise ValueError('Variant survey must be an object')
    required = {'map_name', 'road_id', 'repair_polygon_xy_m', 'route_over_xy_m',
                'route_avoid_xy_m', 'frames', 'ego_blueprint', 'weather_profile',
                'anchor_z_m', 'control_kind', 'control_actor_id',
                'control_xy_m', 'control_type_id'}
    if not required <= survey.keys():
        raise ValueError('Missing variant survey facts: ' + ', '.join(sorted(required - survey.keys())))
    if survey['map_name'] != live_map_name:
        raise ValueError('Live map differs from variant survey')
    if type(survey['road_id']) is not int or type(survey['control_actor_id']) is not int:
        raise ValueError('Road and control need original map/actor identities')
    if type(survey['frames']) is not int or survey['frames'] < 600:
        raise ValueError('Real capture needs at least 30 seconds at 20 Hz')
    if type(survey['anchor_z_m']) not in (int, float) or not math.isfinite(survey['anchor_z_m']):
        raise ValueError('Variant survey needs finite original elevation')
    if not isinstance(survey['ego_blueprint'], str) or not survey['ego_blueprint']:
        raise ValueError('Variant survey needs an ego blueprint')
    if not isinstance(survey['weather_profile'], str) or not survey['weather_profile']:
        raise ValueError('Variant survey needs a weather profile')
    kind = survey['control_kind']
    if kind not in CONTROL_KINDS:
        raise ValueError('Unknown statutory control route')
    expected = ('walker.pedestrian.' if kind in ('warning_person', 'employee_exception')
                else 'static.prop.')
    if not isinstance(survey['control_type_id'], str) or not survey['control_type_id'].startswith(expected):
        raise ValueError('Control actor type does not match route')
    control_xy = _point(survey['control_xy_m'], 'Control location')
    polygon_points = survey['repair_polygon_xy_m']
    if not isinstance(polygon_points, list) or len(polygon_points) < 3:
        raise ValueError('Repair polygon needs at least three points')
    polygon = Polygon([_point(p, 'Repair polygon') for p in polygon_points])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Repair polygon is invalid')
    over = _route(survey['route_over_xy_m'], 'Crossing route')
    avoid = _route(survey['route_avoid_xy_m'], 'Avoidance route')
    if over.length <= 0 or avoid.length <= 0 or not over.crosses(polygon) or avoid.intersects(polygon):
        raise ValueError('Variant routes do not isolate pavement crossing')
    if (Point(over.coords[0]).distance(Point(avoid.coords[0])) > .5 or
            Point(over.coords[-1]).distance(Point(avoid.coords[-1])) > .5):
        raise ValueError('Variant comparison needs shared route endpoints')
    if Point(control_xy).distance(polygon) > 15:
        raise ValueError('Control actor is not near surveyed pavement')
    if kind in SIGN_KINDS:
        if not survey.get('sign_face_source'):
            raise ValueError('Sign route needs original sign-face source reference')
    if kind == 'employee_exception' and not all(survey.get(key) for key in
                                               ('employee_activity_source',
                                                'nonemployee_activity_source')):
        raise ValueError('Employee route needs independent employee and nonemployee activity source references')
    if kind == 'employee_exception':
        warning = survey.get('governing_warning_control')
        if (not isinstance(warning, dict) or
                type(warning.get('actor_id')) is not int or
                warning['actor_id'] == survey['control_actor_id'] or
                not isinstance(warning.get('type_id'), str) or
                not warning['type_id'].startswith(('walker.pedestrian.', 'static.prop.')) or
                not isinstance(warning.get('source_reference'), str) or
                not warning['source_reference'].strip()):
            raise ValueError('Employee route needs a distinct sourced governing warning control')
        warning_xy = _point(warning.get('xy_m'), 'Governing warning location')
        if Point(warning_xy).distance(polygon) > 15:
            raise ValueError('Governing warning control is not near surveyed pavement')
    if kind == 'employee_exception':
        cases = {
            'employee_crossing': {'route_xy_m': survey['route_over_xy_m'],
                                  'requested_pavement_crossing': True,
                                  'operator_activity_source': survey['employee_activity_source']},
            'nonemployee_crossing': {'route_xy_m': survey['route_over_xy_m'],
                                     'requested_pavement_crossing': True,
                                     'operator_activity_source': survey['nonemployee_activity_source']},
        }
    else:
        cases = {
            'crossing': {'route_xy_m': survey['route_over_xy_m'],
                         'requested_pavement_crossing': True},
            'avoidance': {'route_xy_m': survey['route_avoid_xy_m'],
                          'requested_pavement_crossing': False},
        }
    return {'map_name': survey['map_name'], 'road_id': survey['road_id'],
            'repair_polygon_xy_m': polygon_points, 'control_kind': kind,
            'control_actor_id': survey['control_actor_id'],
            'control_type_id': survey['control_type_id'],
            'control_xy_m': control_xy, 'frames': survey['frames'],
            'governing_warning_control': survey.get('governing_warning_control'),
            'capture_rate_hz': 20, 'ego_blueprint': survey['ego_blueprint'],
            'weather_profile': survey['weather_profile'],
            'anchor_z_m': survey['anchor_z_m'],
            'source_references': {key: survey[key] for key in
                                  ('sign_face_source', 'employee_activity_source',
                                   'nonemployee_activity_source') if key in survey},
            'cases': cases,
            'repair_status_verified': False, 'control_content_verified': False,
            'employee_exception_verified': False,
            'physical_completion_claimed': False}


def bind(survey, world, carla):
    """Join survey facts to a live map and control actor before capture."""
    mapping = world.get_map()
    plan = validate(survey, mapping.name)
    elevation = plan['anchor_z_m']
    polygon = plan['repair_polygon_xy_m']
    x = sum(p[0] for p in polygon) / len(polygon)
    y = sum(p[1] for p in polygon) / len(polygon)
    pavement = mapping.get_waypoint(carla.Location(x=x, y=y, z=elevation),
                                    project_to_road=False, lane_type=carla.LaneType.Any)
    if pavement is None or pavement.road_id != plan['road_id']:
        raise ValueError('Live pavement road differs from variant survey')
    routes = {}
    for name, case in plan['cases'].items():
        rows = []
        for x, y in case['route_xy_m']:
            wp = mapping.get_waypoint(carla.Location(x=x, y=y, z=elevation),
                                      project_to_road=False, lane_type=carla.LaneType.Any)
            if wp is None or wp.lane_type not in (carla.LaneType.Driving, carla.LaneType.Shoulder):
                raise ValueError('Variant route leaves live drivable pavement: ' + name)
            rows.append({'road_id': wp.road_id, 'lane_id': wp.lane_id,
                         'lane_type': str(wp.lane_type)})
        routes[name] = rows
    actor = world.get_actors().find(plan['control_actor_id'])
    if actor is None or actor.type_id != plan['control_type_id']:
        raise ValueError('Live control actor differs from variant survey')
    location = actor.get_transform().location
    if hypot(location.x - plan['control_xy_m'][0],
             location.y - plan['control_xy_m'][1]) > .5:
        raise ValueError('Live control actor position differs from variant survey')
    warning_readback = None
    if plan['control_kind'] == 'employee_exception':
        warning = plan['governing_warning_control']
        governing = world.get_actors().find(warning['actor_id'])
        if governing is None or governing.type_id != warning['type_id']:
            raise ValueError('Live governing warning actor differs from variant survey')
        governing_location = governing.get_transform().location
        if hypot(governing_location.x - warning['xy_m'][0],
                 governing_location.y - warning['xy_m'][1]) > .5:
            raise ValueError('Live governing warning position differs from variant survey')
        warning_readback = {'actor_id': governing.id,
                            'type_id': governing.type_id,
                            'xyz_m': [governing_location.x, governing_location.y,
                                      governing_location.z],
                            'source_reference': warning['source_reference']}
    return {'plan': plan, 'source_kind': 'live_carla_map_and_actor_readback',
            'pavement_road_id': pavement.road_id,
            'pavement_lane_id': pavement.lane_id,
            'route_waypoints': routes, 'control_actor_id': actor.id,
            'control_type_id': actor.type_id,
            'control_xyz_m': [location.x, location.y, location.z],
            'governing_warning_control': warning_readback,
            'control_content_verified': False,
            'employee_exception_verified': False,
            'physical_completion_claimed': False}
