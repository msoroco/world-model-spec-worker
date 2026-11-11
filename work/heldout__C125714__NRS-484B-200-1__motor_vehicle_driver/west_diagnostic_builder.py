"""Build a coherent westbound CPU fixture from the supplied two-way road fixture.

This moves only the synthetic subject and attached cameras to the opposite
lane. Road graph and OpenDRIVE geometry already contain both directions.
It is a software diagnostic, never a Native observation.
"""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


WEST_CASE = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__baseline_right_west'
LANE_SHIFT_M = -3.5


def _point(value):
    value = list(value)
    value[1] += LANE_SHIFT_M
    return value


def _vector(value):
    value = list(value)
    value[0], value[1] = -value[0], -value[1]
    return value


def _heading(value):
    return (value + 180) % 360


def _participant(item):
    item['position_m'] = _point(item['position_m'])
    item['heading_deg'] = _heading(item['heading_deg'])
    if 'body_vertices_m' in item:
        item['body_vertices_m'] = [_point(p) for p in item['body_vertices_m']]
    for name in ('velocity_mps', 'acceleration_mps2'):
        if name in item:
            item[name] = _vector(item[name])


def _observation(item):
    for participant in item.get('participants', []):
        if participant.get('actor_id') == 205:
            _participant(participant)
    for sensor in item.get('rgb_sensors', []):
        if sensor.get('parent_actor_id') == 205:
            sensor['position_m'] = _point(sensor['position_m'])
            if 'yaw' in sensor.get('rotation_deg', {}):
                sensor['rotation_deg']['yaw'] = _heading(sensor['rotation_deg']['yaw'])


def _jsonl(text, transform):
    return ''.join(json.dumps(transform(json.loads(line)), allow_nan=False) + '\n'
                   for line in text.splitlines() if line.strip())


def _evidence(row):
    _participant(row['ego'])
    _observation(row['original_observations'])
    row['world']['road_projection']['lane_id'] = 1
    return row


def _trace(row):
    row['position'] = dict(zip(('x', 'y', 'z'), _point([
        row['position']['x'], row['position']['y'], row['position']['z']])))
    row['position_m'] = _point(row['position_m'])
    row['velocity_mps'] = _vector(row['velocity_mps'])
    row['heading_deg'] = _heading(row['heading_deg'])
    return row


def _roadway(row):
    row['travel_tangent_xy'] = [-1.0, 0.0]
    row['left_road_edge_xy'], row['right_road_edge_xy'] = (
        row['right_road_edge_xy'], row['left_road_edge_xy'])
    row['ego_corners'] = [_point(p) for p in row['ego_corners']]
    row['subject_lane_id'], row['opposite_lane_id'] = (
        row['opposite_lane_id'], row['subject_lane_id'])
    return row


def build(east):
    west = deepcopy(east)
    files = west['files']
    files['capture/evidence.jsonl'] = _jsonl(files['capture/evidence.jsonl'], _evidence)
    files['trace.jsonl'] = _jsonl(files['trace.jsonl'], _trace)
    files['directed_roadway_footprints.jsonl'] = _jsonl(
        files['directed_roadway_footprints.jsonl'], _roadway)
    manifest = json.loads(files['capture/manifest.json'])
    manifest['case_id'] = WEST_CASE
    manifest['sources']['trace.jsonl'] = sha256(files['trace.jsonl'].encode()).hexdigest()
    files['capture/manifest.json'] = json.dumps(manifest, indent=2) + '\n'
    files['right-half-diagnostic-provenance.json'] = json.dumps({
        'format': 'worker-diagnostic-source-note',
        'source': 'runtime/fixtures/example.json and east diagnostic.json',
        'use': 'synthetic westbound compatibility only; subject and attached cameras moved to the existing opposite lane; no Native motion, physical or legal acceptance',
        'builder': 'west_diagnostic_builder.py'}, indent=2) + '\n'
    for graph in west['graphs']:
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
            actor['forward'] = _vector(actor['forward'])
            actor['right'] = _vector(actor['right'])
            for stem in ('carla_vel_', 'carla_acc_'):
                actor[stem+'x'], actor[stem+'y'] = -actor[stem+'x'], -actor[stem+'y']
            if 'original_observation' in actor:
                _participant(actor['original_observation'])
    return west


def main():
    root = Path(__file__).parent
    source = root / 'diagnostic.json'
    output = root / 'west-diagnostic.json'
    if output.exists():
        raise ValueError('Retain prior west diagnostic')
    output.write_text(json.dumps(build(json.loads(source.read_text())), allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
