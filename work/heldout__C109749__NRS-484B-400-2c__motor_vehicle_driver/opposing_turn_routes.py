"""Choose two connected Native left-turn paths from a surveyed junction.

The caller supplies paths from actual map waypoint successors. This selector
does not assert that a chosen map and physical turn satisfy the statute.
"""

from math import hypot, isfinite


def _unit(vector):
    if len(vector) != 2 or not all(isinstance(v, (int, float)) and isfinite(v) for v in vector):
        raise ValueError('route heading needs finite XY components')
    length = hypot(*vector)
    if length < 1e-6:
        raise ValueError('zero route heading')
    return (vector[0]/length, vector[1]/length)


def _left(route):
    start, end = _unit(route['approach_heading_xy']), _unit(route['exit_heading_xy'])
    cross = start[0]*end[1]-start[1]*end[0]
    dot = start[0]*end[0]+start[1]*end[1]
    return cross > .5 and abs(dot) < .8


def select_opposing_left_pair(routes, lane_inventory, *, route_accept=None):
    """Return a same-junction opposing pair with opposite-sign road lanes.

    `routes` contain connected Native waypoint `path`, approach/exit road IDs,
    axis identity and measured headings. `lane_inventory` maps each road ID to
    original Native lane IDs. A caller may reject unsuitable junction geometry
    or devices using `route_accept`, but cannot relax the checks here.
    """
    for route in routes:
        if not route.get('path') or route.get('junction_id') is None:
            raise ValueError('route lacks connected Native path or junction')
    for a in routes:
        for b in routes:
            if a is b or a['junction_id'] != b['junction_id'] or (
                    a.get('approach_axis') != b.get('approach_axis')):
                continue
            if not (_left(a) and _left(b)):
                continue
            if ('approach_lane_id' in a and 'approach_lane_id' in b and
                    a['approach_lane_id'] * b['approach_lane_id'] >= 0):
                continue
            heading_a, heading_b = _unit(a['approach_heading_xy']), _unit(b['approach_heading_xy'])
            if heading_a[0]*heading_b[0]+heading_a[1]*heading_b[1] > -.8:
                continue
            roads = {a['approach_road_id'], a['exit_road_id'],
                     b['approach_road_id'], b['exit_road_id']}
            if any(not (any(lane < 0 for lane in lane_inventory.get(road, ())) and
                        any(lane > 0 for lane in lane_inventory.get(road, ()))) for road in roads):
                continue
            if route_accept is not None and not route_accept(a, b):
                continue
            return {'subject': a, 'opposing': b,
                    'junction_id': a['junction_id'],
                    'selection_basis': 'connected Native left-turn successors, opposing headings and two-directional lane inventory',
                    'legal_front_of_each_other': 'unreviewed'}
    raise ValueError('no surveyed opposing two-directional left-turn pair')
