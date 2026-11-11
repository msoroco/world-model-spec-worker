"""Capture original Native actor footprints and velocities for exposure analysis."""

import json
from math import atan2
from pathlib import Path


def _body_corners(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError('Native actor body does not have eight vertices')
    bottom = sorted(vertices, key=lambda point: point.z)[:4]
    cx = sum(point.x for point in bottom) / 4
    cy = sum(point.y for point in bottom) / 4
    bottom.sort(key=lambda point: atan2(point.y - cy, point.x - cx))
    return [[float(point.x), float(point.y)] for point in bottom]


def _velocity(actor):
    velocity = actor.get_velocity()
    return [float(velocity.x), float(velocity.y)]


class ExposureSourceRecorder:
    def __init__(self, output, ego, exposed, exposed_kind):
        if exposed_kind not in ('pedestrian', 'cyclist', 'motor_vehicle', 'property'):
            raise ValueError('Exposed actor kind missing')
        if ego.id == exposed.id:
            raise ValueError('Exposure requires distinct Native actor identities')
        self.ego = ego
        self.exposed = exposed
        self.kind = exposed_kind
        self.path = Path(output) / 'exposed_actor_footprints.jsonl'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise ValueError('Retain prior original exposure source')
        self.file = self.path.open('x', encoding='utf-8')
        self.previous = None

    def append(self, frame, time_s):
        if self.file.closed:
            raise ValueError('Original exposure source closed')
        if self.previous and (frame != self.previous[0] + 1 or
                              abs(time_s - self.previous[1] - .05) > 1e-4):
            raise ValueError('Original exposure sample did not advance at 20 Hz')
        row = {'frame': int(frame), 'time_s': float(time_s),
               'ego_id': str(self.ego.id), 'exposed_id': str(self.exposed.id),
               'exposed_kind': self.kind,
               'ego_corners_xy': _body_corners(self.ego),
               'exposed_corners_xy': _body_corners(self.exposed),
               'ego_velocity_xy_mps': _velocity(self.ego),
               'exposed_velocity_xy_mps': _velocity(self.exposed)}
        self.file.write(json.dumps(row, sort_keys=True) + '\n')
        self.file.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.file.close()
