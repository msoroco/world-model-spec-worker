"""Stage a controlled opposite-direction turn-intent route pair on the CPU.

The route and controller-intent difference is constructed here. Original Native
vehicle motion and the legal exception remain independent later checks.
"""
import copy
import math

from shapely.geometry import LineString, Point, Polygon


def _lateral_offset(scene):
    other = scene['approaches']['other']
    route = other['route_xy_m']
    if len(route) < 3 or any(len(p) != 2 or
                             any(type(v) not in (int, float) or not math.isfinite(v)
                                 for v in p) for p in route):
        raise ValueError('Finite other route required')
    polygon = Polygon(scene['crossing_polygon_xy_m'])
    if (not polygon.is_valid or polygon.area <= 0 or
            polygon.intersects(Point(route[0])) or
            polygon.intersects(Point(route[-1])) or
            not LineString(route).intersects(polygon) or
            not any(polygon.contains(Point(p)) for p in route[1:-1])):
        raise ValueError('Other route must enter and exit the same crossing')
    ox, oy = other['forward_xy']
    if math.hypot(ox, oy) == 0:
        raise ValueError('Original approach heading required')
    return (ox * (route[-1][1] - route[0][1]) -
            oy * (route[-1][0] - route[0][0])) / math.hypot(ox, oy)


def validate_turn_pair(left, straight):
    fixed = ('native_map_name', 'intersection_id', 'same_statutory_crossing',
             'crossing_polygon_xy_m', 'stop_sign', 'ego_stop_line_xy_m',
             'camera_poses', 'other_release_frame', 'ego_hold_after_clear_frames')
    if any(left.get(key) != straight.get(key) for key in fixed):
        raise ValueError('Turn comparison changed a fixed condition')
    if (left.get('approach_relation') != 'opposite_directions' or
            straight.get('approach_relation') != 'opposite_directions'):
        raise ValueError('Opposite-direction approach pair required')
    if left['approaches']['ego'] != straight['approaches']['ego']:
        raise ValueError('Ego route or approach changed')
    a, b = left['approaches']['other'], straight['approaches']['other']
    for key in ('highway_id', 'lane_id', 'road_id', 'spawn_pose', 'forward_xy'):
        if a.get(key) != b.get(key):
            raise ValueError('Other approach identity changed')
    if a['route_xy_m'][:-1] != b['route_xy_m'][:-1]:
        raise ValueError('Other entry path changed')
    if (left.get('other_left_turn_intended') is not True or
            straight.get('other_left_turn_intended') is not False):
        raise ValueError('Opposite left/straight intent commands required')
    left_offset, straight_offset = _lateral_offset(left), _lateral_offset(straight)
    if left_offset <= 1 or abs(straight_offset) > 1:
        raise ValueError('Commanded left and straight exits required')
    return {'comparison_kind': 'opposite_direction_turn_intent',
            'fixed_conditions': list(fixed) + ['ego_approach', 'other_entry_path'],
            'left_exit_offset_m': left_offset,
            'straight_exit_offset_m': straight_offset,
            'observed_turn_status': 'unverified',
            'legal_acceptance_claimed': False,
            'physical_acceptance_claimed': False}


def build_turn_pair(scene, release_frame=40, hold_frames=0):
    if scene.get('approach_relation') != 'opposite_directions':
        raise ValueError('Opposite-direction source scene required')
    left = copy.deepcopy(scene)
    straight = copy.deepcopy(scene)
    for row in (left, straight):
        row['other_release_frame'] = release_frame
        row['ego_hold_after_clear_frames'] = hold_frames
    left['other_left_turn_intended'] = True
    straight['other_left_turn_intended'] = False
    entry = straight['approaches']['other']['route_xy_m'][0]
    middle = straight['approaches']['other']['route_xy_m'][1]
    straight['approaches']['other']['route_xy_m'][-1] = [2 * middle[0] - entry[0],
                                                         2 * middle[1] - entry[1]]
    validate_turn_pair(left, straight)
    return left, straight
