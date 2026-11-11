"""Retain immutable Native actor and station survey originals for C111706."""

import json
from pathlib import Path

from fire_station_geometry import validate_entrance
from fire_station_measurement import _waypoint


def _body(actor):
    transform = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(transform)
    if len(vertices) < 8:
        raise ValueError('Native station actor lacks complete bounding box')
    bottom = sorted(vertices, key=lambda vertex: float(vertex.z))[:4]
    if len({(round(float(vertex.x), 4), round(float(vertex.y), 4))
            for vertex in bottom}) != 4:
        raise ValueError('Native station actor ground body is incomplete')
    return [[float(vertex.x), float(vertex.y)] for vertex in bottom]


class StationSourceRecorder:
    def __init__(self, output, survey):
        self.root = Path(output)
        self.root.mkdir(parents=True, exist_ok=True)
        validate_entrance(*(_waypoint(survey[name]) for name in
                            ('public_before', 'public_at', 'public_after',
                             'driveway_at')), source=survey.get('station_source'))
        path = self.root / 'station_survey.json'
        with path.open('x') as file:
            json.dump(survey, file)
            file.write('\n')
        self.subject = (self.root / 'subject_original.jsonl').open('x')
        self.other = (self.root / 'other_original.jsonl').open('x')
        self.previous = None
        self.identities = None

    def append(self, frame, time_s, subject, other, world_map):
        if type(frame) is not int or not isinstance(time_s, (int, float)):
            raise ValueError('Original station frame/time required')
        if self.previous is not None and (frame != self.previous[0]+1 or
                                          abs(float(time_s)-self.previous[1]-.05) > 1e-4):
            raise ValueError('Original station capture must be consecutive 20 Hz')
        identities = (subject.id, other.id)
        if identities[0] == identities[1] or (self.identities is not None and
                                              identities != self.identities):
            raise ValueError('Distinct stable Native station actors required')
        rows = []
        for actor in (subject, other):
            transform = actor.get_transform()
            location = transform.location
            waypoint = world_map.get_waypoint(location)
            if waypoint is None:
                raise ValueError('Native station actor has no original map lane')
            rows.append({'frame': frame, 'time_s': float(time_s),
                         'native_actor_id': actor.id,
                         'center_xy': [float(location.x), float(location.y)],
                         'heading_deg': float(transform.rotation.yaw),
                         'road_id': int(waypoint.road_id),
                         'lane_id': int(waypoint.lane_id),
                         'body_corners_xy': _body(actor)})
        for file, row in zip((self.subject, self.other), rows):
            file.write(json.dumps(row, allow_nan=False) + '\n')
            file.flush()
        self.identities = identities
        self.previous = (frame, float(time_s))

    def close(self):
        self.subject.close()
        self.other.close()
