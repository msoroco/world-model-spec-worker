"""Retain original participant bodies for saved intersection completion checks."""

import json
import math
from pathlib import Path

INTERSECTION_POLYGON = [[-8.0, -8.0], [8.0, -8.0], [8.0, 8.0], [-8.0, 8.0]]


def _xyz(point):
    values = [float(point.x), float(point.y), float(point.z)]
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Nonfinite original body point')
    return values


def _body(world, actor):
    transform = actor.get_transform()
    vertices = [_xyz(point) for point in actor.bounding_box.get_world_vertices(transform)]
    if len(vertices) < 4:
        raise ValueError('Incomplete original actor body')
    waypoint = world.get_map().get_waypoint(transform.location, project_to_road=False)
    if waypoint is None:
        raise ValueError('Original actor has no Native road waypoint')
    return {'actor_id': actor.id, 'blueprint': actor.type_id,
            'position_m': _xyz(transform.location),
            'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
            'body_vertices_m': vertices}


def observe_interaction(world, ego, through, frame, time_s):
    if world.get_snapshot().frame != frame or type(frame) is not int:
        raise ValueError('Interaction observation frame differs')
    if isinstance(time_s, bool) or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
        raise ValueError('Missing original interaction time')
    ego_state = _body(world, ego)
    through_state = None if through is None else _body(world, through)
    if world.get_snapshot().frame != frame:
        raise ValueError('World advanced during interaction observation')
    return {'frame': frame, 'time_s': float(time_s),
            'ego': ego_state, 'through': through_state}


class InteractionWriter:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / 'interaction_history.jsonl'
        self.context = self.root / 'control_context.json'
        if self.path.exists() or self.context.exists():
            raise ValueError('Retain prior interaction sources')
        self.context.write_text(json.dumps({
            'intersection_xy_m': INTERSECTION_POLYGON,
            'source': 'authored OpenDRIVE junction bounds; Native map facts and body overlap required',
            'engineering_extent_not_legal_line': True}, indent=2) + '\n')
        self.previous = (-1, -math.inf)

    def add(self, row):
        frame, time_s = row.get('frame'), row.get('time_s')
        if (type(frame) is not int or frame <= self.previous[0]
                or isinstance(time_s, bool) or not isinstance(time_s, (int, float))
                or not math.isfinite(time_s) or time_s <= self.previous[1]):
            raise ValueError('Nonmonotone original interaction frame')
        with self.path.open('a') as stream:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
        self.previous = (frame, time_s)
