"""Original two-lane one-way candidate geometry and posted-sign readback."""
import json
from math import atan2, hypot
from pathlib import Path

from road_source_capture import _forward, _xy


def _driving(lane):
    return lane is not None and str(lane.lane_type).split('.')[-1] == 'Driving'


def same_direction_left(right_lane):
    left_lane = right_lane.get_left_lane()
    if (not _driving(left_lane) or left_lane.road_id != right_lane.road_id or
            min(float(right_lane.lane_width), float(left_lane.lane_width)) <= 0 or
            left_lane.lane_id == right_lane.lane_id):
        raise ValueError('One-way left driving lane missing or invalid')
    tangent, other = _forward(right_lane), _forward(left_lane)
    if sum(a * b for a, b in zip(tangent, other)) < .95:
        raise ValueError('One-way adjacent lane travels another direction')
    left = (-tangent[1], tangent[0])
    a, b = _xy(right_lane.transform.location), _xy(left_lane.transform.location)
    lateral = sum((b[i] - a[i]) * left[i] for i in (0, 1))
    if abs(lateral - (float(right_lane.lane_width) + float(left_lane.lane_width)) / 2) > .4:
        raise ValueError('One-way lane centers are not joined')
    if _driving(right_lane.get_right_lane()) or _driving(left_lane.get_left_lane()):
        raise ValueError('One-way exact scene has additional driving lane')
    return left_lane


def select_one_way_route(world_map, *, steps=16, spacing_m=2.5):
    if type(steps) is not int or steps < 10 or spacing_m <= 0:
        raise ValueError('Invalid one-way route request')
    for spawn in world_map.get_spawn_points():
        start = world_map.get_waypoint(spawn.location)
        if start is None or start.is_junction:
            continue
        try:
            same_direction_left(start)
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
                same_direction_left(options[0])
            except ValueError:
                break
            route.append(options[0])
        if len(route) == steps + 1:
            return route
    raise ValueError('No bounded two-lane same-direction Native route')


def one_way_targets(route):
    if len(route) < 11:
        raise ValueError('One-way route too short')
    targets = [list(_xy(same_direction_left(lane).transform.location))
               for lane in route]
    if any(hypot(b[0] - a[0], b[1] - a[1]) < .25
           for a, b in zip(targets, targets[1:])):
        raise ValueError('One-way targets have stationary step')
    return {'targets_xy_m': targets, 'body_side': 'left',
            'other_vehicle_start_xy_m': list(_xy(route[8].transform.location)),
            'designation_verified': False, 'posting_authority_verified': False}


def spawn_one_way_sign(world, carla, right_lane):
    library = world.get_blueprint_library()
    blueprints = list(library.filter('*oneway*')) + list(library.filter('*one_way*'))
    unique = {item.id: item for item in blueprints}
    if not unique:
        raise ValueError('Native one-way sign blueprint unavailable')
    tangent = _forward(right_lane)
    left = (-tangent[1], tangent[0])
    point = right_lane.transform.location
    distance = float(right_lane.lane_width) / 2 + .5
    transform = carla.Transform(carla.Location(
        x=point.x + tangent[0] * 5 - left[0] * distance,
        y=point.y + tangent[1] * 5 - left[1] * distance,
        z=point.z + .1), right_lane.transform.rotation)
    actor = world.try_spawn_actor(unique[sorted(unique)[0]], transform)
    if actor is None:
        raise ValueError('Native one-way sign spawn failed')
    return actor


def sample_one_way(actor, sign, right_lane, frame, time_s):
    left_lane = same_direction_left(right_lane)
    tangent = _forward(right_lane)
    left = (-tangent[1], tangent[0])
    a, b = (_xy(lane.transform.location) for lane in (right_lane, left_lane))
    right_edge = [a[i] - left[i] * float(right_lane.lane_width) / 2 for i in (0, 1)]
    left_edge = [b[i] + left[i] * float(left_lane.lane_width) / 2 for i in (0, 1)]
    midpoint = [(right_edge[i] + left_edge[i]) / 2 for i in (0, 1)]
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    footprint = sorted(set(_xy(vertex) for vertex in vertices)) if len(vertices) == 8 else []
    if len(footprint) != 4:
        raise ValueError('Native one-way body footprint needs eight vertices and four corners')
    cx = sum(point[0] for point in footprint) / 4
    cy = sum(point[1] for point in footprint) / 4
    footprint.sort(key=lambda point: atan2(point[1] - cy, point[0] - cx))
    sign_position = sign.get_transform().location
    if 'oneway' not in sign.type_id.lower().replace('_', ''):
        raise ValueError('Original Native sign actor changed type')
    road = {'frame': int(frame), 'time_s': float(time_s),
            'road_id': right_lane.road_id, 'lane_id': left_lane.lane_id,
            'road_center_xy': midpoint, 'road_travel_tangent_xy': list(tangent),
            'road_width_m': float(right_lane.lane_width) + float(left_lane.lane_width),
            'ego_corners_xy': [list(point) for point in footprint],
            'lane_inventory': [
                {'lane_id': lane.lane_id, 'width_m': float(lane.lane_width),
                 'travel_tangent_xy': list(_forward(lane))}
                for lane in (right_lane, left_lane)],
            'designation_verified': False, 'posting_authority_verified': False}
    sign_row = {'frame': int(frame), 'time_s': float(time_s),
                'actor_id': str(sign.id), 'blueprint_id': sign.type_id,
                'position_m': [float(sign_position.x), float(sign_position.y), float(sign_position.z)],
                'designation_verified': False, 'posting_authority_verified': False}
    return road, sign_row


class OneWayRoadRecorder:
    def __init__(self, output, sign):
        root = Path(output)
        self.road = (root / 'ego_road_frames.jsonl').open('x', encoding='utf-8')
        self.sign = (root / 'one_way_sign.jsonl').open('x', encoding='utf-8')
        self.actor = sign
        self.previous = None

    def append(self, actor, waypoint, frame, time_s):
        if self.previous is not None and (
                frame != self.previous[0] + 1 or
                abs(time_s - self.previous[1] - .05) > 1e-4):
            raise ValueError('One-way original source not continuous at 20 Hz')
        road, sign = sample_one_way(actor, self.actor, waypoint, frame, time_s)
        self.road.write(json.dumps(road, separators=(',', ':')) + '\n')
        self.sign.write(json.dumps(sign, separators=(',', ':')) + '\n')
        self.road.flush()
        self.sign.flush()
        self.previous = frame, time_s
        return road, sign

    def close(self):
        self.road.close()
        self.sign.close()
