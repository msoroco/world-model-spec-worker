"""Measured narrow two-way road candidate; legal sufficiency stays undecided."""
from math import hypot

from road_source_capture import _opposing_neighbor
from right_half_route import baseline_targets


MAX_CANDIDATE_WIDTH_M = 6.5


def measured_width(waypoint):
    other = _opposing_neighbor(waypoint)
    own, opposing = float(waypoint.lane_width), float(other.lane_width)
    if min(own, opposing) <= 0:
        raise ValueError('Narrow road source lane width invalid')
    return own + opposing


def select_narrow_route(world_map, *, steps=16, spacing_m=2.5,
                        max_candidate_width_m=MAX_CANDIDATE_WIDTH_M):
    if type(steps) is not int or steps < 10 or spacing_m <= 0 or max_candidate_width_m <= 0:
        raise ValueError('Invalid narrow road candidate request')
    for spawn in world_map.get_spawn_points():
        start = world_map.get_waypoint(spawn.location)
        if start is None or start.is_junction:
            continue
        try:
            width = measured_width(start)
        except ValueError:
            continue
        if width > max_candidate_width_m:
            continue
        route = [start]
        for _ in range(steps):
            options = [item for item in route[-1].next(spacing_m)
                       if item.road_id == start.road_id and item.lane_id == start.lane_id
                       and not item.is_junction]
            if len(options) != 1:
                break
            try:
                width = measured_width(options[0])
            except ValueError:
                break
            if width > max_candidate_width_m:
                break
            route.append(options[0])
        if len(route) == steps + 1:
            return route
    raise ValueError('No connected measured narrow two-way road candidate')


def narrow_targets(route, *, max_candidate_width_m=MAX_CANDIDATE_WIDTH_M):
    widths = [measured_width(item) for item in route]
    if not widths or max(widths) > max_candidate_width_m:
        raise ValueError('Narrow candidate route width exceeds screen')
    targets = baseline_targets(route, body_side='left')
    targets['measured_road_width_m'] = widths
    targets['max_candidate_width_m'] = max_candidate_width_m
    targets['legal_sufficiency_decided'] = False
    return targets


def body_width_m(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError('Native body width needs eight original vertices')
    points = {(float(point.x), float(point.y)) for point in vertices}
    if len(points) != 4:
        raise ValueError('Native body width needs four footprint corners')
    distances = sorted(hypot(b[0] - a[0], b[1] - a[1]) for a in points for b in points if a != b)
    if len(distances) != 12 or distances[0] <= 0:
        raise ValueError('Native body footprint invalid')
    return distances[0]
