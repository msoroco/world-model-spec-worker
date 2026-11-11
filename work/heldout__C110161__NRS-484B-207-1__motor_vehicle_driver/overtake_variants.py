"""Measured control targets for the three overtaking comparison variants.

These are engineering sweep settings. They do not define statutory safety.
"""

from math import hypot, isfinite


def return_target(route, ego_xy, ego_rear_long_m, other_front_long_m, *,
                  passed_abreast, requested_return_clearance_m, lookahead=3):
    """Use a signed body clearance so an early-return case is constructible."""
    if (not isfinite(requested_return_clearance_m) or
            not -4 <= requested_return_clearance_m <= 10 or lookahead < 1):
        raise ValueError('Invalid signed return clearance sweep')
    if not all(isfinite(x) for x in (*ego_xy, ego_rear_long_m, other_front_long_m)):
        raise ValueError('Nonfinite original return geometry')
    right = route['right']
    nearest = min(range(len(right)), key=lambda i: hypot(
        ego_xy[0] - right[i].transform.location.x,
        ego_xy[1] - right[i].transform.location.y))
    index = min(nearest + lookahead, len(right) - 1)
    clearance = ego_rear_long_m - other_front_long_m
    return_right = passed_abreast and clearance >= requested_return_clearance_m
    return {'waypoint': (right if return_right else route['left'])[index],
            'phase': 'return_right' if return_right else 'pass_left',
            'waypoint_index': index, 'measured_body_clearance_m': clearance}


def left_target_xy(waypoint, original_row, desired_surface_gap_m):
    """Aim the subject center at a measured gap left of the other body."""
    if not isfinite(desired_surface_gap_m) or not 0 <= desired_surface_gap_m <= 3:
        raise ValueError('Invalid lateral gap sweep')
    hx, hy = original_row['road_tangent_xy']
    length = hypot(hx, hy)
    if not isfinite(length) or length < .99:
        raise ValueError('Invalid original road tangent')
    lx, ly = -hy / length, hx / length
    other = original_row['other_corners']
    ego = original_row['ego_corners']
    if len(other) < 4 or len(ego) < 4:
        raise ValueError('Missing original body corners')
    points = [tuple(point) for point in (*other, *ego)]
    if any(len(point) != 2 or not all(isfinite(v) for v in point)
           for point in points):
        raise ValueError('Nonfinite original body corners')
    other_left = max(x * lx + y * ly for x, y in other)
    ego_center_left = sum(x * lx + y * ly for x, y in ego) / len(ego)
    ego_half_width = max(x * lx + y * ly for x, y in ego) - ego_center_left
    desired_left = other_left + ego_half_width + desired_surface_gap_m
    loc = waypoint.transform.location
    current_left = loc.x * lx + loc.y * ly
    offset = desired_left - current_left
    if abs(offset) > 3:
        raise ValueError('Lateral comparison target outside construction sweep')
    return [loc.x + offset * lx, loc.y + offset * ly]
