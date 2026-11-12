"""Build a synthetic moving-actor fixture for saved passing-path diagnostics.

The recipe is only a CPU source-shape check; its motion is generated here and
does not represent a Native capture or establish a lawful pass.
"""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


PASSING_CASE = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__passing_same_direction'


def _shift(point, dx):
    point = list(point)
    point[0] += dx
    return point


def _participant(item, dx):
    item['position_m'] = _shift(item['position_m'], dx)
    if 'body_vertices_m' in item:
        item['body_vertices_m'] = [_shift(p, dx) for p in item['body_vertices_m']]


def _observation(item, dx):
    for participant in item.get('participants', []):
        if participant.get('actor_id') == 205:
            _participant(participant, dx)
    for sensor in item.get('rgb_sensors', []):
        if sensor.get('parent_actor_id') == 205:
            sensor['position_m'] = _shift(sensor['position_m'], dx)


def build(left):
    result = deepcopy(left)
    files = result['files']
    evidence = [json.loads(line) for line in files['capture/evidence.jsonl'].splitlines() if line]
    trace = [json.loads(line) for line in files['trace.jsonl'].splitlines() if line]
    roadway = [json.loads(line) for line in files['directed_roadway_footprints.jsonl'].splitlines() if line]
    passing = []
    if not evidence or not len(evidence) == len(trace) == len(roadway):
        raise ValueError('Passing diagnostic source lengths differ')
    origin_x = trace[0]['position_m'][0]
    for index, (source, motion, road) in enumerate(zip(evidence, trace, roadway)):
        dx = index*.5
        _participant(source['ego'], dx)
        source['ego']['speed_mps'] = 10.0
        _observation(source['original_observations'], dx)
        motion['position']['x'] += dx
        motion['position_m'] = _shift(motion['position_m'], dx)
        motion['velocity_mps'][0] = 10.0
        motion['speed_mps'] = 10.0
        motion['speed_mph'] = 10.0/.44704
        road['ego_corners'] = [_shift(p, dx) for p in road['ego_corners']]
        subject_x, subject_y, subject_z = motion['position_m']
        lead_x = origin_x + 2 + index*.125
        passing.append({'frame': road['frame'], 'time_s': road['time_s'],
            'subject': {'actor_id': road['ego_id'], 'blueprint_id': 'vehicle.tesla.model3',
                        'position_m': [subject_x, subject_y, subject_z],
                        'velocity_mps': [10.0, 0.0, 0.0]},
            'lead': {'actor_id': 'fixture-lead-206', 'blueprint_id': 'vehicle.tesla.model3',
                     'position_m': [lead_x, subject_y+2.0, subject_z],
                     'velocity_mps': [2.5, 0.0, 0.0]},
            'passing_law_verified': False})
    first_frame = roadway[0]['frame']
    for graph in result['graphs']:
        attributes = graph['attributes']
        index = int(attributes['frame']) - first_frame
        if not 0 <= index < len(roadway):
            raise ValueError('Passing graph frame differs from sources')
        dx = index*.5
        _observation(attributes.get('observed_evidence', {}), dx)
        if 'ego' in attributes.get('bbox', {}):
            attributes['bbox']['ego'] = [_shift(p, dx) for p in attributes['bbox']['ego']]
        for node in graph.get('nodes', []):
            if node.get('id') == 'ego':
                entry = node['attributes']
                entry['vertex'] = _shift(entry['vertex'], dx)
                entry['threedbbox'] = [_shift(p, dx) for p in entry['threedbbox']]
                if 'original_observation' in entry:
                    _participant(entry['original_observation'], dx)
    for name, rows in [('capture/evidence.jsonl', evidence), ('trace.jsonl', trace),
                       ('directed_roadway_footprints.jsonl', roadway),
                       ('passing_actors.jsonl', passing)]:
        files[name] = ''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows)
    manifest = json.loads(files['capture/manifest.json'])
    manifest['case_id'] = PASSING_CASE
    manifest['sources']['trace.jsonl'] = sha256(files['trace.jsonl'].encode()).hexdigest()
    files['capture/manifest.json'] = json.dumps(manifest, indent=2)+'\n'
    files['passing-diagnostic-provenance.json'] = json.dumps({
        'format': 'worker-diagnostic-source-note',
        'use': 'synthetic moving same-direction vehicles for CPU saved processing only',
        'physical_acceptance_claimed': False, 'passing_law_verified': False,
        'builder': 'passing_diagnostic_builder.py'}, indent=2)+'\n'
    return result


def main():
    root = Path(__file__).parent
    output = root/'passing-diagnostic.json'
    if output.exists():
        raise ValueError('Retain prior passing diagnostic')
    output.write_text(json.dumps(build(json.loads((root/'left-diagnostic.json').read_text())),
                                 allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
