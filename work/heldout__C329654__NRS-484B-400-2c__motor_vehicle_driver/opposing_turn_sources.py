"""Retain original Native actor and map/device inputs for opposing turns."""

import json
from math import cos, radians, sin
from pathlib import Path


class OpposingTurnRecorder:
    def __init__(self, output, topology, devices):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        names = ('subject_original.jsonl', 'opposing_original.jsonl',
                 'topology_original.json', 'devices_original.json')
        if any((self.output / name).exists() for name in names):
            raise FileExistsError('original opposing-turn sources already exist')
        if not topology.get('source_map') or 'governing_device' not in devices:
            raise ValueError('map and device source inventory required')
        (self.output / names[2]).write_text(json.dumps(topology, sort_keys=True) + '\n')
        (self.output / names[3]).write_text(json.dumps(devices, sort_keys=True) + '\n')
        self.subject = (self.output / names[0]).open('x')
        self.opposing = (self.output / names[1]).open('x')
        self.last_frame = None
        self.last_time = None
        self.closed = False

    @staticmethod
    def _actor_row(actor, frame, time_s, in_intersection, turning_left):
        transform = actor.get_transform()
        location = transform.location
        heading = (cos(radians(transform.rotation.yaw)),
                   sin(radians(transform.rotation.yaw)))
        vertices = actor.bounding_box.get_world_vertices(transform)
        if len(vertices) != 8:
            raise ValueError('Native actor body needs eight world vertices')
        bottom = sorted(vertices, key=lambda point: point.z)[:4]
        center_x = sum(point.x for point in bottom)/4
        center_y = sum(point.y for point in bottom)/4
        # CARLA world-vertex order is not a planar polygon order. Sort the
        # footprint counterclockwise before saved surface-distance processing.
        from math import atan2
        bottom.sort(key=lambda point: atan2(point.y-center_y, point.x-center_x))
        return {'frame': frame, 'time_s': time_s,
                'center_xy': [location.x, location.y],
                'heading_xy': list(heading),
                'ground_corners_xy': [[point.x, point.y] for point in bottom],
                'in_intersection': bool(in_intersection),
                'turning_left': bool(turning_left),
                'native_actor_id': actor.id}

    def append(self, frame, time_s, subject, opposing, *, subject_in_intersection,
               opposing_in_intersection, subject_turning_left, opposing_turning_left):
        if self.closed:
            raise ValueError('original recorder is closed')
        if type(frame) is not int or frame < 0 or not isinstance(time_s, (int, float)):
            raise ValueError('invalid Native frame/time')
        if self.last_frame is not None and (frame <= self.last_frame or time_s <= self.last_time):
            raise ValueError('Native frames/times must increase together')
        a = self._actor_row(subject, frame, time_s, subject_in_intersection,
                            subject_turning_left)
        b = self._actor_row(opposing, frame, time_s, opposing_in_intersection,
                            opposing_turning_left)
        self.subject.write(json.dumps(a, allow_nan=False) + '\n')
        self.opposing.write(json.dumps(b, allow_nan=False) + '\n')
        self.last_frame, self.last_time = frame, time_s

    def close(self):
        if not self.closed:
            self.subject.close()
            self.opposing.close()
            self.closed = True
