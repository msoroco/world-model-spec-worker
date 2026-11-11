"""Original Native actor geometry and road-tangent source for overtaking."""

import json
from math import atan2, isfinite
from pathlib import Path


def _corners(actor):
    vertices = list(actor.bounding_box.get_world_vertices(actor.get_transform()))
    if len(vertices) != 8 or any(not all(isfinite(float(getattr(v, axis)))
                                      for axis in ('x', 'y', 'z')) for v in vertices):
        raise ValueError('Native overtake body vertices invalid')
    lower = sorted(vertices, key=lambda point: point.z)[:4]
    cx = sum(point.x for point in lower) / 4
    cy = sum(point.y for point in lower) / 4
    lower.sort(key=lambda point: atan2(point.y - cy, point.x - cx))
    return [[float(point.x), float(point.y)] for point in lower]


def _heading(transform):
    vector = transform.get_forward_vector()
    if not all(isfinite(float(value)) for value in (vector.x, vector.y)):
        raise ValueError('Native overtake heading invalid')
    return [float(vector.x), float(vector.y)]


class OvertakeSourceRecorder:
    def __init__(self, output, ego, other, world_map):
        if not ego.id or not other.id or ego.id == other.id:
            raise ValueError('Overtake actors need distinct Native identities')
        self.ego, self.other, self.world_map = ego, other, world_map
        path = Path(output)
        path.mkdir(parents=True, exist_ok=True)
        self.output = (path / 'participant_footprints.jsonl').open('x')
        self.previous = None

    def append(self, frame, time_s):
        if (type(frame) is not int or type(time_s) not in (int, float) or
                not isfinite(time_s) or
                self.previous and (frame != self.previous[0] + 1 or
                                   abs(time_s - self.previous[1] - .05) > 1e-4)):
            raise ValueError('Original overtake source is not joined at 20 Hz')
        ego_transform = self.ego.get_transform()
        other_transform = self.other.get_transform()
        waypoint = self.world_map.get_waypoint(ego_transform.location)
        if waypoint is None or waypoint.is_junction:
            raise ValueError('Original overtake road tangent unavailable')
        row = {'frame': frame, 'time_s': time_s,
               'ego_id': str(self.ego.id), 'other_id': str(self.other.id),
               'ego_corners': _corners(self.ego),
               'other_corners': _corners(self.other),
               'ego_heading_xy': _heading(ego_transform),
               'other_heading_xy': _heading(other_transform),
               'road_tangent_xy': _heading(waypoint.transform),
               'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id}
        self.output.write(json.dumps(row, allow_nan=False) + '\n')
        self.output.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.output.close()
