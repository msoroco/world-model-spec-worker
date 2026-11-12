"""Shift only synthetic subject/camera sources into the mapped center lane."""

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path


HERE = Path(__file__).resolve().parent
SHIFT_M = 7.0


def point(value):
    result = list(value)
    result[1] += SHIFT_M
    return result


def participant(value):
    value['position_m'] = point(value['position_m'])
    if 'body_vertices_m' in value:
        value['body_vertices_m'] = [point(vertex) for vertex in value['body_vertices_m']]


def observations(value):
    for item in value.get('participants', []):
        if item.get('actor_id') == 205:
            participant(item)
    for item in value.get('rgb_sensors', []):
        if item.get('parent_actor_id') == 205:
            item['position_m'] = point(item['position_m'])


def jsonl(text, transform):
    return ''.join(json.dumps(transform(json.loads(line)), allow_nan=False) + '\n'
                   for line in text.splitlines() if line.strip())


def build(baseline):
    changed = deepcopy(baseline)
    files = changed['files']
    def evidence(row):
        participant(row['ego'])
        observations(row['original_observations'])
        return row
    def trace(row):
        row['position'] = dict(zip(('x', 'y', 'z'), point([
            row['position']['x'], row['position']['y'], row['position']['z']])))
        row['position_m'] = point(row['position_m'])
        return row
    def lane(row):
        row['ego_corners_xy'] = [point(vertex) for vertex in row['ego_corners_xy']]
        return row
    files['capture/evidence.jsonl'] = jsonl(files['capture/evidence.jsonl'], evidence)
    files['trace.jsonl'] = jsonl(files['trace.jsonl'], trace)
    files['three_lane_frames.jsonl'] = jsonl(files['three_lane_frames.jsonl'], lane)
    manifest = json.loads(files['capture/manifest.json'])
    manifest['case_id'] = HERE.name + '__extreme_left'
    manifest['sources']['trace.jsonl'] = sha256(files['trace.jsonl'].encode()).hexdigest()
    files['capture/manifest.json'] = json.dumps(manifest, indent=2) + '\n'
    files['three-lane-diagnostic-provenance.json'] = json.dumps({
        'format': 'worker-diagnostic-source-note',
        'source': 'right-baseline-diagnostic.json',
        'use': 'synthetic prepositioned extreme-left counterflow body, trace, original ego and camera sources; no Native or legal claim',
        'builder': 'build_extreme_left_diagnostic.py'}) + '\n'
    for graph in changed['graphs']:
        attributes = graph['attributes']
        if 'observed_evidence' in attributes:
            observations(attributes['observed_evidence'])
        if 'ego' in attributes.get('bbox', {}):
            attributes['bbox']['ego'] = [point(vertex) for vertex in attributes['bbox']['ego']]
        for node in graph.get('nodes', []):
            if node.get('id') != 'ego':
                continue
            actor = node['attributes']
            actor['vertex'] = point(actor['vertex'])
            actor['threedbbox'] = [point(vertex) for vertex in actor['threedbbox']]
            if 'original_observation' in actor:
                participant(actor['original_observation'])
    return changed


def main():
    source = json.loads((HERE / 'right-baseline-diagnostic.json').read_text())
    target = HERE / 'extreme-left-diagnostic.json'
    target.write_text(json.dumps(build(source), separators=(',', ':'), allow_nan=False) + '\n')
    print(target)


if __name__ == '__main__':
    main()
