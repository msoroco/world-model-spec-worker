"""Author tiny case-specific synthetic Native-shaped CPU fixtures, never originals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from access_aisle import CASES

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':')) + '\n', encoding='utf-8')


def site():
    data = {'cell_id': 'C150072', 'actor': 'motor_vehicle_driver',
            'aisle_polygon_xy': [[0, 0], [3, 0], [3, 6], [0, 6]],
            'adjacent_space_polygon_xy': [[3, 0], [6, 0], [6, 6], [3, 6]],
            'approach_route_xy': [[-5, 3], [-2, 3], [0, 3]],
            'target_footprints': {
                'aisle_full': {'source_sha256': 'synthetic-full', 'polygon_xy': [[.5, 1], [2.5, 1], [2.5, 5], [.5, 5]]},
                'aisle_partial': {'source_sha256': 'synthetic-partial', 'polygon_xy': [[2.5, 1], [4.5, 1], [4.5, 5], [2.5, 5]]},
                'adjacent_space': {'source_sha256': 'synthetic-adjacent', 'polygon_xy': [[3.5, 1], [5.5, 1], [5.5, 5], [3.5, 5]]}}}
    for name in ('jurisdiction', 'map', 'aisle_marking', 'adjacent_designated_space',
                 'accessible_route', 'ingress_egress_design', 'vehicle_blueprint', 'approach_route'):
        data[name + '_source_sha256'] = 'synthetic-' + name
    data['designation_relies_on_135a'] = False
    return data


def main():
    base = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
    mapping = [json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines() if line]
    for item in CASES:
        spec = json.loads(json.dumps(base))
        for unrelated in ('alley_context.json', 'body_history.jsonl', 'speed_samples.jsonl'):
            spec['files'].pop(unrelated, None)
        fixture_site = site()
        fixture_site['requested_footprint'] = item.target
        fixture_site['requested_activity'] = item.requested_activity
        footprint = fixture_site['target_footprints'][item.target]['polygon_xy']
        rows = []
        for frame in mapping:
            rows.append({'original_frame': frame['carla_frame'], 'time_s': frame['time_s'],
                         'source_sha256': 'synthetic-diagnostic',
                         'body_geometry_source_sha256': 'synthetic-body',
                         'control_source_sha256': 'synthetic-control',
                         'activity_source_sha256': 'synthetic-activity',
                         'map_source_sha256': fixture_site['map_source_sha256'],
                         'aisle_marking_source_sha256': fixture_site['aisle_marking_source_sha256'],
                         'ego_id': 'synthetic-ego',
                         'ego_speed_mps': 1 if item.requested_activity == 'travel' else 0,
                         'observed_activity': item.requested_activity,
                         'vehicle_body_polygon_xy': footprint})
        spec['files']['access-aisle-site.json'] = json.dumps(fixture_site) + '\n'
        spec['files']['access-aisle-history.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
        spec['files']['diagnostic-source-note.json'] = json.dumps({
            'source_kind': 'synthetic_diagnostic_fixture', 'accepted_original_source': False,
            'case_id': ROOT.name + '__' + item.case_id}) + '\n'
        output = ROOT / ('diagnostic-' + item.case_id + '.json')
        write(output, spec)
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': str(output.relative_to(REPO)), 'sha256': digest}],
                  'generator': {'source': str(output.relative_to(REPO)), 'sha256': digest}}
        write(ROOT / ('diagnostic-' + item.case_id + '-recipe.json'), recipe)


if __name__ == '__main__':
    main()
