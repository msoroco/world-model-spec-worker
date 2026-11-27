"""Generate eight source-inventoried synthetic compatibility specifications."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parking import CASES

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n',
                    encoding='utf-8')


def site():
    return {
        'cell_id': 'C135705', 'layout': 'narrow_road',
        'highway_status': 'source_reviewed',
        'highway_source_sha256': 'synthetic-highway',
        'map_source_sha256': 'synthetic-map',
        'edge_source_sha256': 'synthetic-edge',
        'edge_point_xy': [0, 0], 'roadward_unit_xy': [0, 1],
        'edge_vehicle_xy': [10, .7], 'ego_side_xy': [10, 3.0],
        'ego_behind_xy': [20, .7], 'ego_approach_xy': [0, 3.0],
        'approach_route_xy': [[0, 3.0], [5, 3.0], [10, 3.0]],
        'approach_route_source_sha256': 'synthetic-route',
        'ego_blueprint_source_sha256': 'synthetic-ego',
        'edge_blueprint_source_sha256': 'synthetic-edge-vehicle'}


def main():
    base = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
    mapping = [json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines()]
    for item in CASES:
        spec = json.loads(json.dumps(base))
        for unrelated in ('alley_context.json', 'body_history.jsonl', 'speed_samples.jsonl'):
            spec['files'].pop(unrelated, None)
        data = site()
        target = data['ego_behind_xy'] if item.endpoint == 'behind_edge_vehicle' else data['ego_side_xy']
        history = []
        for row in mapping:
            history.append({
                'original_frame': row['carla_frame'], 'time_s': row['time_s'],
                'ego_id': 'synthetic-ego', 'edge_vehicle_id': 'synthetic-edge-vehicle',
                'ego_xy': target, 'edge_vehicle_xy': data['edge_vehicle_xy'],
                'ego_speed_mps': 0.0, 'edge_speed_mps': 0.0,
                'source_sha256': 'synthetic-actor-frame',
                'highway_source_sha256': data['highway_source_sha256'],
                'map_source_sha256': data['map_source_sha256'],
                'edge_source_sha256': data['edge_source_sha256'],
                'ego_control_source_sha256': 'synthetic-control',
                'exception_source_sha256': 'synthetic-authority' if item.exception_probe else None,
                'requested_activity': item.activity,
                'requested_exception_probe': item.exception_probe})
        spec['files']['parking-site.json'] = json.dumps({'site': data}) + '\n'
        spec['files']['parking-history.jsonl'] = ''.join(json.dumps(row) + '\n' for row in history)
        spec['files']['diagnostic-source-note.json'] = json.dumps({
            'source_kind': 'synthetic_diagnostic_fixture',
            'accepted_original_source': False,
            'case_id': ROOT.name + '__' + item.case_id}) + '\n'
        spec['files']['carla_recorder.log'] = 'synthetic diagnostic recorder placeholder\n'
        source = ROOT / ('diagnostic-' + item.case_id + '.json')
        write(source, spec)
        checksum = hashlib.sha256(source.read_bytes()).hexdigest()
        source_name = str(source.relative_to(REPO))
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': source_name, 'sha256': checksum}],
                  'generator': {'source': source_name, 'sha256': checksum}}
        write(ROOT / ('diagnostic-' + item.case_id + '-recipe.json'), recipe)


if __name__ == '__main__':
    main()
