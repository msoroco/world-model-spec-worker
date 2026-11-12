"""Retain original Native actor geometry for C229126's pass sequence.

The recorder is CARLA lazy: callers supply live actors and a map.  Its rows
are original acquisition, not a claim that the planned pass was realized.
"""

import json
from math import atan2, hypot, isfinite
from pathlib import Path


def _corners(actor):
    vertices = list(actor.bounding_box.get_world_vertices(actor.get_transform()))
    if len(vertices) != 8 or any(not all(isfinite(float(getattr(v, axis)))
                                      for axis in ('x', 'y', 'z')) for v in vertices):
        raise ValueError('Original actor bounding box invalid')
    lower = sorted(vertices, key=lambda point: point.z)[:4]
    cx = sum(point.x for point in lower) / 4
    cy = sum(point.y for point in lower) / 4
    lower.sort(key=lambda point: atan2(point.y - cy, point.x - cx))
    return [[float(point.x), float(point.y)] for point in lower]


def _heading(transform):
    vector = transform.get_forward_vector()
    length = hypot(vector.x, vector.y)
    if not isfinite(length) or length < 1e-6:
        raise ValueError('Original actor or road heading invalid')
    return [float(vector.x / length), float(vector.y / length)]


class OvertakeSourceRecorder:
    def __init__(self, output, ego, other, world_map):
        if not ego.id or not other.id or ego.id == other.id:
            raise ValueError('Two distinct original actor identities required')
        self.ego, self.other, self.world_map = ego, other, world_map
        self.path = Path(output) / 'participant_footprints.jsonl'
        self.stream = self.path.open('x', encoding='utf-8')
        self.previous = None

    def append(self, frame, time_s):
        if (type(frame) is not int or frame < 0 or type(time_s) not in (int, float)
                or not isfinite(time_s) or self.previous and
                (frame != self.previous[0] + 1 or
                 abs(time_s - self.previous[1] - .05) > 1e-4)):
            raise ValueError('Original 20 Hz actor/frame join failed')
        ego_tf, other_tf = self.ego.get_transform(), self.other.get_transform()
        ego_waypoint = self.world_map.get_waypoint(ego_tf.location)
        other_waypoint = self.world_map.get_waypoint(other_tf.location)
        if (ego_waypoint is None or other_waypoint is None or
                ego_waypoint.is_junction or other_waypoint.is_junction or
                ego_waypoint.road_id != other_waypoint.road_id):
            raise ValueError('Original same-road lane membership missing')
        road_heading = _heading(other_waypoint.transform)
        other_heading = _heading(other_tf)
        if sum(a * b for a, b in zip(road_heading, other_heading)) < .95:
            raise ValueError('Overtaken actor is not proceeding with road tangent')
        speed = self.other.get_velocity()
        other_speed = hypot(speed.x, speed.y)
        if not isfinite(other_speed) or other_speed <= 0:
            raise ValueError('Original overtaken actor speed missing')
        row = {
            'frame': frame, 'time_s': time_s,
            'ego_id': str(self.ego.id), 'other_id': str(self.other.id),
            'ego_corners': _corners(self.ego),
            'other_corners': _corners(self.other),
            'ego_heading_xy': _heading(ego_tf),
            'other_heading_xy': other_heading,
            'road_tangent_xy': road_heading,
            'road_id': other_waypoint.road_id,
            'ego_lane_id': ego_waypoint.lane_id,
            'other_lane_id': other_waypoint.lane_id,
            'other_speed_mps': other_speed,
        }
        self.stream.write(json.dumps(row, allow_nan=False) + '\n')
        self.stream.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.stream.close()
