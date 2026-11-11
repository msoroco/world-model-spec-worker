"""Build a synthetic left-overlap source fixture on the same eastbound road.

The fixture tests full-body measurement and saved-source joins only. Its
prepositioned body does not establish that the Native controller reaches it.
"""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


LEFT_CASE = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__unexcepted_left'
LEFT_SHIFT_M = -1.2


def _point(value):
    value = list(value)
    value[1] += LEFT_SHIFT_M
    return value


def _participant(item):
    item['position_m'] = _point(item['position_m'])
    if 'body_vertices_m' in item:
        item['body_vertices_m'] = [_point(p) for p in item['body_vertices_m']]


def _observation(item):
    for participant in item.get('participants', []):
        if participant.get('actor_id') == 205:
            _participant(participant)
    for sensor in item.get('rgb_sensors', []):
        if sensor.get('parent_actor_id') == 205:
            sensor['position_m'] = _point(sensor['position_m'])


def _jsonl(text, transform):
    return ''.join(json.dumps(transform(json.loads(line)), allow_nan=False) + '\n'
                   for line in text.splitlines() if line.strip())


def _evidence(row):
    _participant(row['ego'])
    _observation(row['original_observations'])
    return row


def _trace(row):
    row['position'] = dict(zip(('x', 'y', 'z'), _point([
        row['position']['x'], row['position']['y'], row['position']['z']])))
    row['position_m'] = _point(row['position_m'])
    return row


def _roadway(row):
    row['ego_corners'] = [_point(p) for p in row['ego_corners']]
    return row


def build(east):
    left = deepcopy(east)
    files = left['files']
    files['capture/evidence.jsonl'] = _jsonl(files['capture/evidence.jsonl'], _evidence)
    files['trace.jsonl'] = _jsonl(files['trace.jsonl'], _trace)
    files['directed_roadway_footprints.jsonl'] = _jsonl(
        files['directed_roadway_footprints.jsonl'], _roadway)
    manifest = json.loads(files['capture/manifest.json'])
    manifest['case_id'] = LEFT_CASE
    manifest['sources']['trace.jsonl'] = sha256(files['trace.jsonl'].encode()).hexdigest()
    files['capture/manifest.json'] = json.dumps(manifest, indent=2) + '\n'
    files['right-half-diagnostic-provenance.json'] = json.dumps({
        'format': 'worker-diagnostic-source-note',
        'source': 'runtime/fixtures/example.json and east diagnostic.json',
        'use': 'synthetic prepositioned full-body left overlap for compatibility only; no Native controller motion, physical or legal acceptance',
        'builder': 'left_diagnostic_builder.py'}, indent=2) + '\n'
    for graph in left['graphs']:
        attributes = graph['attributes']
        if 'observed_evidence' in attributes:
            _observation(attributes['observed_evidence'])
        if 'ego' in attributes.get('bbox', {}):
            attributes['bbox']['ego'] = [_point(p) for p in attributes['bbox']['ego']]
        for node in graph.get('nodes', []):
            if node.get('id') != 'ego':
                continue
            actor = node['attributes']
            actor['vertex'] = _point(actor['vertex'])
            actor['threedbbox'] = [_point(p) for p in actor['threedbbox']]
            if 'original_observation' in actor:
                _participant(actor['original_observation'])
    return left


def main():
    root = Path(__file__).parent
    source = root / 'diagnostic.json'
    output = root / 'left-diagnostic.json'
    if output.exists():
        raise ValueError('Retain prior left diagnostic')
    output.write_text(json.dumps(build(json.loads(source.read_text())), allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
