"""Generate eight source-inventoried synthetic compatibility specifications."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tunnel import CASES

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n',
                    encoding='utf-8')


def site():
    hashes = {name: hashlib.sha256(('synthetic diagnostic ' + name).encode()).hexdigest()
              for name in ('map', 'highway', 'tunnel', 'portal', 'route',
                           'ego_blueprint', 'other_blueprint')}
    return {
        'cell_id': 'C312865', 'layout': 'tunnel',
        'highway_status': 'source_reviewed_public_vehicular_use',
        **{name + '_source_sha256': digest for name, digest in hashes.items()},
        'tunnel_polygon_xy': [[0, -5], [100, -5], [100, 5], [0, 5]],
        'ego_approach_xy': [-30, 0], 'outside_target_xy': [-10, 0],
        'inside_target_xy': [50, 0], 'other_vehicle_xy': [70, 2],
        'approach_route_xy': [[-30, 0], [-10, 0], [50, 0]],
        'other_vehicle_route_xy': [[70, 2], [80, 2]]}


def main():
    base = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
    mapping = [json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines()]
    for item in CASES:
        spec = json.loads(json.dumps(base))
        for video in spec['videos']:
            if video['path'] == 'reference_corner.mkv':
                video['path'] = 'reference_corner.mkv'
        for unrelated in ('alley_context.json', 'body_history.jsonl', 'speed_samples.jsonl'):
            spec['files'].pop(unrelated, None)
        data = site()
        target = data['outside_target_xy'] if item.endpoint == 'outside_before_portal' else data['inside_target_xy']
        vertices = [[target[0] - 1, -1], [target[0] + 1, -1],
                    [target[0] + 1, 1], [target[0] - 1, 1]]
        history = []
        for row in mapping:
            history.append({
                'original_frame': row['carla_frame'], 'time_s': row['time_s'],
                'ego_id': 'synthetic-ego', 'other_vehicle_id': 'synthetic-other-vehicle',
                'ego_xy': target, 'other_vehicle_xy': data['other_vehicle_xy'],
                'ego_body_vertices_xy': vertices,
                'ego_speed_mps': 0.0, 'other_vehicle_speed_mps': 0.0,
                'other_vehicle_purpose': 'unknown',
                'source_sha256': 'synthetic-actor-frame',
                'highway_source_sha256': data['highway_source_sha256'],
                'map_source_sha256': data['map_source_sha256'],
                'tunnel_source_sha256': data['tunnel_source_sha256'],
                'portal_source_sha256': data['portal_source_sha256'],
                'ego_control_source_sha256': 'synthetic-control',
                'exception_source_sha256': 'synthetic-authority' if item.exception_probe else None,
                'requested_activity': item.activity,
                'activity_readback': 'unresolved',
                'requested_exception_probe': item.exception_probe})
        spec['files']['tunnel-site.json'] = json.dumps({'site': data}) + '\n'
        spec['files']['tunnel-history.jsonl'] = ''.join(json.dumps(row) + '\n' for row in history)
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
