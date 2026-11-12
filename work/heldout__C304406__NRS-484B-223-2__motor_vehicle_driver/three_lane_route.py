"""Select a connected, marked three-lane Native highway section.

The selector returns map geometry and marking readback. It does not infer that
paint is physically visible in a camera or that a lane use is lawful.
"""

from math import hypot


def _xy(waypoint):
    location = waypoint.transform.location
    return float(location.x), float(location.y)


def _unit(waypoint):
    vector = waypoint.transform.get_forward_vector()
    norm = hypot(vector.x, vector.y)
    if norm < 0.8:
        raise ValueError('Map travel tangent unavailable')
    return vector.x / norm, vector.y / norm


def _marked(marking):
    if marking is None:
        return False
    kind = getattr(marking, 'type', marking)
    value = str(kind).lower()
    return bool(value) and 'none' not in value and 'unknown' not in value


def ordered_lanes(right_lane):
    """Read exactly three adjacent driving lanes, ordered for ego travel."""
    center = right_lane.get_left_lane()
    extreme_left = center.get_left_lane() if center is not None else None
    lanes = (right_lane, center, extreme_left)
    if any(lane is None or str(getattr(lane, 'lane_type', '')).lower().find('driving') < 0
           for lane in lanes):
        raise ValueError('Three adjacent driving lanes required')
    if len({(lane.road_id, lane.lane_id) for lane in lanes}) != 3 or len({lane.road_id for lane in lanes}) != 1:
        raise ValueError('Three adjacent lanes must share one road identity')
    def driving(lane):
        return lane is not None and 'driving' in str(getattr(lane, 'lane_type', '')).lower()
    if driving(right_lane.get_right_lane()) or driving(extreme_left.get_left_lane()):
        raise ValueError('Three-lane section has an additional mapped lane')
    tangent = _unit(right_lane)
    left = (-tangent[1], tangent[0])
    for first, second in zip(lanes, lanes[1:]):
        if first.lane_width <= 0 or second.lane_width <= 0:
            raise ValueError('Mapped lane width invalid')
        a, b = _xy(first), _xy(second)
        separation = (b[0] - a[0]) * left[0] + (b[1] - a[1]) * left[1]
        expected = (first.lane_width + second.lane_width) / 2
        if abs(separation - expected) > 0.45:
            raise ValueError('Mapped lane adjacency or ordering differs')
    if sum(a * b for a, b in zip(tangent, _unit(center))) < 0.95:
        raise ValueError('Center lane is not in ego travel direction')
    for lane in lanes:
        if not _marked(lane.left_lane_marking) or not _marked(lane.right_lane_marking):
            raise ValueError('Three clearly marked lanes lack map marking readback')
    return {'right': right_lane, 'center': center, 'extreme_left': extreme_left}


def select_route(world_map, *, direction='east', steps=12, spacing_m=2.5):
    """Find a same-road corridor; test both directions with direction parameter."""
    if direction not in ('east', 'west') or steps < 2 or spacing_m <= 0:
        raise ValueError('Three-lane route selector parameters invalid')
    for spawn in world_map.get_spawn_points():
        start = world_map.get_waypoint(spawn.location)
        if start is None or start.is_junction:
            continue
        forward = _unit(start)
        if (direction == 'east' and forward[0] <= 0.8) or (direction == 'west' and forward[0] >= -0.8):
            continue
        try:
            ordered_lanes(start)
        except ValueError:
            continue
        route = [start]
        for _ in range(steps):
            options = [waypoint for waypoint in route[-1].next(spacing_m)
                       if waypoint.road_id == start.road_id and waypoint.lane_id == start.lane_id
                       and not waypoint.is_junction]
            if not options:
                break
            try:
                ordered_lanes(options[0])
            except ValueError:
                break
            route.append(options[0])
        if len(route) == steps + 1:
            return route
    raise ValueError('No connected marked three-lane corridor in selected direction')


def section_readback(right_lane):
    lanes = ordered_lanes(right_lane)
    return {'road_id': right_lane.road_id,
            'lane_ids': {name: lane.lane_id for name, lane in lanes.items()},
            'lane_widths_m': {name: float(lane.lane_width) for name, lane in lanes.items()},
            'lane_directions_xy': {name: list(_unit(lane)) for name, lane in lanes.items()},
            'markings': {name: {'left': str(lane.left_lane_marking.type),
                                'right': str(lane.right_lane_marking.type)}
                         for name, lane in lanes.items()},
            'map_markings_verified': True,
            'physical_paint_visible': None,
            'legal_lane_status': None}
