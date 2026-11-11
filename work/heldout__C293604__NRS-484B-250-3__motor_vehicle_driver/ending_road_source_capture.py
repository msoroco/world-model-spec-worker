"""Retain original Native T-junction topology and participant body frames.

OpenDRIVE road IDs are operational topology keys. They do not establish a
legal highway classification or the statutory approximately-same-time test.
"""

from __future__ import annotations

import json
from math import atan2, hypot, isfinite
from pathlib import Path

from ending_road_measurement import classify_approaches


def _body(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    points = sorted({(float(vertex.x), float(vertex.y)) for vertex in vertices})
    if len(points) != 4 or any(not all(isfinite(x) for x in point) for point in points):
        raise ValueError('Native participant needs four finite ground corners')
    cx = sum(x for x, _ in points) / 4
    cy = sum(y for _, y in points) / 4
    return [list(point) for point in sorted(points,
            key=lambda point: atan2(point[1] - cy, point[0] - cx))]


def _linked(first, second):
    target = second.transform.location
    for candidate in first.next(2.0):
        location = candidate.transform.location
        if (candidate.road_id, candidate.lane_id) == (second.road_id, second.lane_id) and hypot(
                location.x - target.x, location.y - target.y) < 0.75:
            return True
    return False


def _junction_id(waypoint):
    if not waypoint.is_junction:
        return None
    junction = waypoint.get_junction()
    if junction is None:
        raise ValueError('Native junction waypoint has no junction readback')
    return str(junction.id)


def _path_nodes(role, path, expected_junction):
    if len(path) < 3 or path[0].is_junction or path[-1].is_junction:
        raise ValueError('Native approach needs exterior, junction and exterior waypoints')
    ids = [f'{role}-{index}' for index in range(len(path))]
    nodes = {}
    seen_junction = False
    if any(not _linked(first, second) for first, second in zip(path, path[1:])):
        raise ValueError('Native route waypoints are not connected successors')
    for index, waypoint in enumerate(path):
        junction = _junction_id(waypoint)
        if junction is not None:
            seen_junction = True
            if junction != expected_junction:
                raise ValueError('Native paths enter different junctions')
        if waypoint.road_id is None or waypoint.lane_id is None:
            raise ValueError('Native waypoint lacks road or lane readback')
        nodes[ids[index]] = {'highway_id': 'native-road:' + str(waypoint.road_id),
                             'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
                             'junction_id': junction,
                             'successors': [ids[index + 1]] if index + 1 < len(path) else []}
    if not seen_junction or path[-1].road_id == path[0].road_id and role == 'subject':
        raise ValueError('Subject path lacks an ending-road junction traversal')
    return ids[0], nodes


def topology_from_native(subject_path, other_path, subject_actor, other_actor,
                         junction, conflict_polygon_xy):
    junction_id = str(junction.id)
    subject, subject_nodes = _path_nodes('subject', subject_path, junction_id)
    other, other_nodes = _path_nodes('other', other_path, junction_id)
    nodes = {**subject_nodes, **other_nodes}
    if len(conflict_polygon_xy) < 3 or any(
            len(point) != 2 or not all(isfinite(float(x)) for x in point)
            for point in conflict_polygon_xy):
        raise ValueError('Native conflict zone polygon is missing or nonfinite')
    topology = {'format': 'worker-ending-road-original-topology',
                'highway_identity_source': 'Native OpenDRIVE road_id readback; operational continuity only',
                'junction_id': junction_id, 'lanes': nodes,
                'subject_approach_lane': subject, 'other_approach_lane': other,
                'subject_id': str(subject_actor.id), 'other_id': str(other_actor.id),
                'conflict_polygon_xy': [list(map(float, point)) for point in conflict_polygon_xy],
                'legal_highway_classification_claimed': False}
    classify_approaches(topology)
    return topology


class EndingRoadSourceRecorder:
    def __init__(self, output, topology, subject_actor, other_actor):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.topology_path = self.output / 'intersection_topology.json'
        self.rows_path = self.output / 'intersection_participants.jsonl'
        if self.topology_path.exists() or self.rows_path.exists():
            raise FileExistsError('Retain prior original ending-road source')
        if topology['subject_id'] != str(subject_actor.id) or topology['other_id'] != str(other_actor.id):
            raise ValueError('Native actor identities differ from selected topology')
        classify_approaches(topology)
        self.subject = subject_actor
        self.other = other_actor
        self.topology_path.write_text(json.dumps(topology, indent=2, allow_nan=False) + '\n')
        self.stream = self.rows_path.open('x')
        self.previous = None

    def append(self, frame, time_s):
        if type(frame) is not int or not isfinite(time_s):
            raise ValueError('Original Native frame/time readback invalid')
        if self.previous is not None and (frame != self.previous[0] + 1 or
                                          abs(time_s - self.previous[1] - .05) > 1e-4):
            raise ValueError('Original Native ending-road source is not 20 Hz')
        row = {'frame': frame, 'time_s': time_s,
               'subject_id': str(self.subject.id), 'other_id': str(self.other.id),
               'subject_corners': _body(self.subject), 'other_corners': _body(self.other)}
        self.stream.write(json.dumps(row, allow_nan=False) + '\n')
        self.stream.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.stream.close()
