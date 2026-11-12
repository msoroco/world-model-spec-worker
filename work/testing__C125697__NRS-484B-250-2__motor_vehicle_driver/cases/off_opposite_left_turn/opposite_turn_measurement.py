"""Measure an observed westbound-to-southbound left turn from retained Native rows."""
import math


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Finite ' + label + ' required')
    return float(value)


def measure_opposite_turn_context(context, history, controls):
    if (context.get('opposite_approach_with_left_turn') is not True or
            context.get('ego_highway_id') != context.get('other_highway_id') or
            context.get('ego_road_id') != context.get('other_road_id')):
        raise ValueError('Same-road opposite approach with sourced turn intent required')
    route = context.get('other_left_turn_route_xy_m')
    if (not isinstance(route, list) or len(route) < 4 or
            route[0][0] <= route[1][0] or route[-1][1] >= route[-2][1]):
        raise ValueError('Authored westbound-to-southbound route required')
    if len(history) < 3 or len(history) != len(controls):
        raise ValueError('Original turn and control histories required')
    originals = []
    for row, control in zip(history, controls):
        if (row.get('frame') != control.get('frame') or
                row.get('time_s') != control.get('time_s')):
            raise ValueError('Original turn/control frame join failed')
        other = row.get('other')
        if not isinstance(other, dict):
            raise ValueError('Other Native actor source required')
        xy = other.get('position_xy_m')
        if not isinstance(xy, list) or len(xy) != 2:
            raise ValueError('Original other position required')
        originals.append((row['frame'], _number(xy[0], 'other x'),
                          _number(xy[1], 'other y'),
                          _number(other.get('heading_deg'), 'other heading'),
                          _number(control.get('other_steer'), 'other steering')))
    start, end = originals[0], originals[-1]
    if (start[1] - end[1] < 5 or start[2] - end[2] < 5 or
            abs((start[3] % 360) - 180) > 30 or
            abs((end[3] % 360) - 270) > 30 or
            not any(sample[4] < -0.05 for sample in originals)):
        raise ValueError('Original frames do not show a westbound left turn to south')
    return {'opposite_approach_with_left_turn_setup': True,
            'observed_turn_frames': [start[0], end[0]],
            'observed_heading_deg': [start[3], end[3]],
            'westward_displacement_m': start[1] - end[1],
            'southward_displacement_m': start[2] - end[2],
            'original_negative_steering_observed': True,
            'exception_judgment': 'unresolved'}
