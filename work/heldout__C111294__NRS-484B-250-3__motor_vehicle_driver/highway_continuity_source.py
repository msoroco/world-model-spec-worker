"""Retain Native route witnesses for the ending/continuing approach comparison.

Road IDs here are operational map identities; legal highway identity remains a
separate review question. All three routes are retained so the fixed through
approach can be checked from the originals after capture.
"""

import json
from hashlib import sha256
from math import isfinite
from pathlib import Path

from ending_road_source_capture import _body, _linked, _junction_id
from ending_road_measurement import _overlap, _polygon


def _route_rows(path, junction_id):
    if len(path) < 3 or path[0].is_junction or path[-1].is_junction:
        raise ValueError('Comparison route needs exterior, junction and exit')
    if any(not _linked(a, b) for a, b in zip(path, path[1:])):
        raise ValueError('Comparison route has a disconnected Native successor')
    rows = []
    for waypoint in path:
        actual_junction = _junction_id(waypoint)
        if actual_junction is not None and actual_junction != junction_id:
            raise ValueError('Comparison routes enter different junctions')
        location = waypoint.transform.location
        rows.append({'road_id': waypoint.road_id, 'lane_id': waypoint.lane_id,
                     'junction_id': actual_junction,
                     'xy': [float(location.x), float(location.y)]})
    if not any(row['junction_id'] == junction_id for row in rows):
        raise ValueError('Comparison route misses selected junction')
    return rows


def topology_from_pair(pair, selected_category, subject, other, polygon):
    if selected_category not in ('ending', 'continuing'):
        raise ValueError('Unknown highway continuity point category')
    junction = pair['junction_id']
    routes = {name: _route_rows(pair[name], junction)
              for name in ('ending', 'continuing', 'other')}
    witness_paths = [_route_rows(path, junction) for path in pair.get('witness_paths', [])]
    if not witness_paths:
        raise ValueError('Original Native branch witnesses missing')
    ending, continuing, through = (routes[name] for name in
                                   ('ending', 'continuing', 'other'))
    if ending[0]['road_id'] == ending[-1]['road_id']:
        raise ValueError('Ending point continues beyond junction')
    if continuing[0]['road_id'] != continuing[-1]['road_id']:
        raise ValueError('Continuing point turns away from its highway')
    if through[0]['road_id'] != through[-1]['road_id']:
        raise ValueError('Fixed other highway does not continue')
    if len({route[0]['road_id'] for route in routes.values()}) != 3:
        raise ValueError('Comparison point approaches have conflicting road IDs')
    for name, expected in (('ending', False), ('continuing', True), ('other', True)):
        road = routes[name][0]['road_id']
        witness_exits = [path[-1]['road_id'] == road for path in witness_paths
                         if path[0]['road_id'] == road]
        if not witness_exits or any(witness_exits) != expected:
            raise ValueError('Native branch witnesses contradict ' + name + ' category')
    _polygon(polygon, 'comparison conflict zone')
    return {'format': 'worker-highway-continuity-original-topology',
            'junction_id': junction, 'map_name': pair['map_name'],
            'selected_category': selected_category, 'routes': routes,
            'witness_paths': witness_paths,
            'subject_id': str(subject.id), 'other_id': str(other.id),
            'conflict_polygon_xy': polygon,
            'legal_highway_classification_claimed': False}


class ContinuitySourceRecorder:
    def __init__(self, output, topology, subject, other):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.topology_path = self.output / 'highway_pair_topology.json'
        self.rows_path = self.output / 'intersection_participants.jsonl'
        if self.topology_path.exists() or self.rows_path.exists():
            raise FileExistsError('Retain prior original comparison sources')
        if (topology['subject_id'], topology['other_id']) != (str(subject.id), str(other.id)):
            raise ValueError('Comparison actor identity differs from topology')
        self.topology_path.write_text(json.dumps(topology, indent=2, allow_nan=False) + '\n')
        self.stream = self.rows_path.open('x')
        self.subject, self.other = subject, other
        self.previous = None

    def append(self, frame, time_s):
        if self.previous is not None and (frame != self.previous[0] + 1 or
                                          abs(time_s - self.previous[1] - .05) > 1e-4):
            raise ValueError('Comparison source is not consecutive 20 Hz Native data')
        row = {'frame': frame, 'time_s': time_s,
               'subject_id': str(self.subject.id), 'other_id': str(self.other.id),
               'subject_corners': _body(self.subject), 'other_corners': _body(self.other)}
        self.stream.write(json.dumps(row, allow_nan=False) + '\n')
        self.stream.flush()
        self.previous = frame, time_s
        return row

    def close(self):
        self.stream.close()


def measure_originals(topology_path, participants_path):
    """Recompute category and conflict occupancy from retained original bytes."""
    topology_path, participants_path = Path(topology_path), Path(participants_path)
    if not topology_path.is_file() or not topology_path.read_bytes():
        raise ValueError('Missing required source: highway_pair_topology.json')
    if not participants_path.is_file() or not participants_path.read_bytes():
        raise ValueError('Missing required source: intersection_participants.jsonl')
    topology = json.loads(topology_path.read_text())
    if topology.get('format') != 'worker-highway-continuity-original-topology':
        raise ValueError('Original highway-pair topology format differs')
    routes = topology.get('routes', {})
    junction = topology.get('junction_id')
    if set(routes) != {'ending', 'continuing', 'other'} or not junction:
        raise ValueError('Original highway-pair routes missing')
    for name, path in routes.items():
        if (len(path) < 3 or path[0].get('junction_id') is not None or
                path[-1].get('junction_id') is not None or
                not any(row.get('junction_id') == junction for row in path)):
            raise ValueError('Original highway-pair junction traversal differs')
    if (routes['ending'][0]['road_id'] == routes['ending'][-1]['road_id'] or
            routes['continuing'][0]['road_id'] != routes['continuing'][-1]['road_id'] or
            routes['other'][0]['road_id'] != routes['other'][-1]['road_id']):
        raise ValueError('Original highway continuity category differs')
    witnesses = topology.get('witness_paths')
    if not isinstance(witnesses, list) or not witnesses:
        raise ValueError('Original Native branch witnesses missing')
    for name, expected in (('ending', False), ('continuing', True), ('other', True)):
        road = routes[name][0]['road_id']
        witness_exits = [path[-1]['road_id'] == road for path in witnesses
                         if isinstance(path, list) and len(path) >= 3 and
                         path[0].get('road_id') == road]
        if not witness_exits or any(witness_exits) != expected:
            raise ValueError('Original Native branch witnesses contradict ' + name + ' category')
    if topology.get('selected_category') != 'continuing':
        raise ValueError('Wrong selected highway continuity category')
    zone = _polygon(topology.get('conflict_polygon_xy'), 'comparison conflict zone')
    rows = [json.loads(line) for line in participants_path.read_text().splitlines()
            if line.strip()]
    if len(rows) < 3:
        raise ValueError('Highway comparison needs approach, entry and exit frames')
    observations = []
    previous = None
    for row in rows:
        frame, time_s = row.get('frame'), row.get('time_s')
        if (type(frame) is not int or type(time_s) not in (int, float) or
                not isfinite(time_s)):
            raise ValueError('Original highway-comparison frame/time missing')
        if previous is not None and (frame != previous[0] + 1 or
                                      abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError('Original highway-comparison frames are not 20 Hz')
        previous = frame, time_s
        if (row.get('subject_id'), row.get('other_id')) != (
                topology.get('subject_id'), topology.get('other_id')):
            raise ValueError('Original highway-comparison participant changed')
        observations.append({'frame': frame, 'time_s': time_s,
                             'subject_in_conflict': _overlap(
                                 _polygon(row.get('subject_corners'), 'subject body'), zone),
                             'other_in_conflict': _overlap(
                                 _polygon(row.get('other_corners'), 'other body'), zone)})
    def first(key):
        active = [row for row in observations if row[key]]
        if not active:
            raise ValueError('Original participant never enters conflict zone: ' + key)
        return active[0]['time_s'], active[-1]['time_s'], active[0]['frame']
    subject_enter, _, subject_frame = first('subject_in_conflict')
    other_enter, other_last, other_frame = first('other_in_conflict')
    return {'format': 'worker-highway-continuity-observation',
            'topology_sha256': sha256(topology_path.read_bytes()).hexdigest(),
            'frames_sha256': sha256(participants_path.read_bytes()).hexdigest(),
            'selected_category': 'continuing',
            'subject_entry_frame': subject_frame, 'other_entry_frame': other_frame,
            'entry_delta_s': subject_enter - other_enter,
            'subject_entered_after_other_last_conflict_frame': subject_enter > other_last,
            'conflict_overlap_observed': any(r['subject_in_conflict'] and
                                             r['other_in_conflict'] for r in observations),
            'observations': observations,
            'legal_highway_classification_claimed': False,
            'approximately_same_time_legal_judgment': None}
