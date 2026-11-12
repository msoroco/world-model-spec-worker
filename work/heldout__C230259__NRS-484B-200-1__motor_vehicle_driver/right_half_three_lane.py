"""Original three-lane road/body source for the C230259 left-half case."""
import json
from math import atan2, hypot
from pathlib import Path

from road_source_capture import _forward, _xy


def _driving(waypoint):
    return waypoint is not None and str(waypoint.lane_type).split('.')[-1] == 'Driving'


def three_lane_neighbors(right_lane):
    center = right_lane.get_left_lane()
    far_left = center.get_left_lane() if center is not None else None
    if (not _driving(center) or not _driving(far_left) or
            any(lane.road_id != right_lane.road_id or float(lane.lane_width) <= 0
                for lane in (right_lane, center, far_left)) or
            len({right_lane.lane_id, center.lane_id, far_left.lane_id}) != 3):
        raise ValueError('Three distinct driving lanes on one road required')
    tangent = _forward(right_lane)
    middle, opposite = _forward(center), _forward(far_left)
    if (sum(a * b for a, b in zip(tangent, middle)) < .95 or
            sum(a * b for a, b in zip(tangent, opposite)) > -.95):
        raise ValueError('Three-lane traffic direction pattern differs')
    left = (-tangent[1], tangent[0])
    for first, second in ((right_lane, center), (center, far_left)):
        a, b = _xy(first.transform.location), _xy(second.transform.location)
        separation = sum((b[i] - a[i]) * left[i] for i in (0, 1))
        if abs(separation - (float(first.lane_width) + float(second.lane_width)) / 2) > .4:
            raise ValueError('Three-lane centers are not joined')
    if _driving(right_lane.get_right_lane()) or _driving(far_left.get_left_lane()):
        raise ValueError('Additional driving lane defeats exact three-lane scene')
    return center, far_left


def select_three_lane_route(world_map, *, steps=16, spacing_m=2.5):
    if type(steps) is not int or steps < 10 or spacing_m <= 0:
        raise ValueError('Invalid three-lane route request')
    for spawn in world_map.get_spawn_points():
        start = world_map.get_waypoint(spawn.location)
        if start is None or start.is_junction:
            continue
        try:
            three_lane_neighbors(start)
        except ValueError:
            continue
        route = [start]
        for _ in range(steps):
            options = [item for item in route[-1].next(spacing_m)
                       if item.road_id == start.road_id and item.lane_id == start.lane_id
                       and not item.is_junction]
            if len(options) != 1:
                break
            try:
                three_lane_neighbors(options[0])
            except ValueError:
                break
            route.append(options[0])
        if len(route) == steps + 1:
            return route
    raise ValueError('No connected three-lane route with two outbound and one opposing lane')


def three_lane_targets(route):
    if len(route) < 11:
        raise ValueError('Three-lane route too short')
    targets = [list(_xy(three_lane_neighbors(waypoint)[1].transform.location))
               for waypoint in route]
    if any(hypot(b[0] - a[0], b[1] - a[1]) < .25
           for a, b in zip(targets, targets[1:])):
        raise ValueError('Three-lane left targets have stationary step')
    return {'targets_xy_m': targets, 'body_side': 'left',
            'other_vehicle_start_xy_m': list(_xy(route[8].transform.location)),
            'applicable_lane_rule_verified': False}


def sample_three_lane(actor, right_lane, frame, time_s):
    center, far_left = three_lane_neighbors(right_lane)
    tangent = _forward(right_lane)
    left = (-tangent[1], tangent[0])
    right_center, far_center = (_xy(item.transform.location)
                                for item in (right_lane, far_left))
    right_edge = [right_center[i] - left[i] * float(right_lane.lane_width) / 2
                  for i in (0, 1)]
    left_edge = [far_center[i] + left[i] * float(far_left.lane_width) / 2
                 for i in (0, 1)]
    width = sum(float(item.lane_width) for item in (right_lane, center, far_left))
    midpoint = [(right_edge[i] + left_edge[i]) / 2 for i in (0, 1)]
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError('Native three-lane body needs eight vertices')
    footprint = sorted(set(_xy(vertex) for vertex in vertices))
    if len(footprint) != 4:
        raise ValueError('Native three-lane footprint needs four corners')
    cx = sum(point[0] for point in footprint) / 4
    cy = sum(point[1] for point in footprint) / 4
    footprint.sort(key=lambda point: atan2(point[1] - cy, point[0] - cx))
    return {'frame': int(frame), 'time_s': float(time_s),
            'road_id': right_lane.road_id, 'lane_id': far_left.lane_id,
            'road_center_xy': midpoint, 'road_travel_tangent_xy': list(tangent),
            'road_width_m': width, 'ego_corners_xy': [list(point) for point in footprint],
            'lane_inventory': [
                {'lane_id': item.lane_id, 'width_m': float(item.lane_width),
                 'travel_tangent_xy': list(_forward(item))}
                for item in (right_lane, center, far_left)],
            'source_kind': 'Native three-lane waypoints and original actor body',
            'applicable_lane_rule_verified': False,
            'legal_width_or_exception_decided': False}


class ThreeLaneRoadRecorder:
    def __init__(self, output):
        self.path = Path(output) / 'ego_road_frames.jsonl'
        self.stream = self.path.open('x', encoding='utf-8')
        self.previous = None

    def append(self, actor, waypoint, frame, time_s):
        if self.previous is not None and (
                frame != self.previous[0] + 1 or
                abs(time_s - self.previous[1] - .05) > 1e-4):
            raise ValueError('Three-lane original source not continuous at 20 Hz')
        row = sample_three_lane(actor, waypoint, frame, time_s)
        self.stream.write(json.dumps(row, separators=(',', ':')) + '\n')
        self.stream.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        if not self.stream.closed:
            self.stream.close()
