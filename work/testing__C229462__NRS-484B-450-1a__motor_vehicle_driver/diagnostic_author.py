"""Case-specific synthetic CPU compatibility fixtures, never original evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sidewalk_case import CASES, EXCEPTIONS

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':')) + '\n', encoding='utf-8')


def site(item):
    data = {'cell_id': 'C229462', 'actor': 'motor_vehicle_driver',
            'sidewalk_area_id': 'synthetic-sidewalk', 'sidewalk_polygon_xy': [[0, 0], [3, 0], [3, 6], [0, 6]],
            'approach_route_xy': [[-5, 3], [-2, 3], [0, 3]],
            'target_footprints': {
                'overlap': {'source_sha256': 'synthetic-overlap', 'polygon_xy': [[.5, 1], [2.5, 1], [2.5, 5], [.5, 5]]},
                'touch': {'source_sha256': 'synthetic-touch', 'polygon_xy': [[3, 1], [5, 1], [5, 5], [3, 5]]},
                'separate': {'source_sha256': 'synthetic-separate', 'polygon_xy': [[4, 1], [6, 1], [6, 5], [4, 5]]}},
            'requested_relation': item.relation,
            'exception_context': {name: item.traffic_context if name == 'traffic_conflict_necessity' else 'absent'
                                  for name in EXCEPTIONS},
            'jurisdiction': 'synthetic', 'highway_status': 'synthetic',
            'pedestrian_use': 'synthetic', 'parking_purpose': 'synthetic',
            'conflict_vehicle_start_xy': [-4, 0], 'conflict_vehicle_end_xy': [5, 0]}
    for name in ('jurisdiction', 'highway_status', 'curb', 'lateral_highway_lines',
                 'property_lines', 'pedestrian_use', 'map', 'sidewalk_polygon',
                 'vehicle_blueprint', 'approach_route', 'parking_purpose',
                 'exception_context', 'conflict_vehicle_motion'):
        data[name + '_source_sha256'] = 'synthetic-' + name
    return data


def main():
    base = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
    mapping = [json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines() if line]
    for item in CASES:
        spec = json.loads(json.dumps(base))
        for unrelated in ('alley_context.json', 'body_history.jsonl', 'speed_samples.jsonl'):
            spec['files'].pop(unrelated, None)
        fixture_site = site(item)
        footprint = fixture_site['target_footprints'][item.relation]['polygon_xy']
        rows = []
        for frame in mapping:
            rows.append({'original_frame': frame['carla_frame'], 'time_s': frame['time_s'],
                         'source_sha256': 'synthetic-diagnostic',
                         'body_geometry_source_sha256': 'synthetic-body',
                         'activity_source_sha256': 'synthetic-activity',
                         'sidewalk_source_sha256': fixture_site['sidewalk_polygon_source_sha256'],
                         'exception_source_sha256': fixture_site['exception_context_source_sha256'],
                         'ego_id': 'synthetic-ego', 'vehicle_type': 'motor_vehicle',
                         'ego_speed_mps': 0, 'observed_activity': 'park',
                         'vehicle_body_polygon_xy': footprint,
                         'exception_context': fixture_site['exception_context'],
                         'conflict_vehicle_id': 'synthetic-conflict' if item.traffic_context == 'unresolved' else None,
                         'conflict_speed_mps': 2 if item.traffic_context == 'unresolved' else None,
                         'conflict_motion_source_sha256': fixture_site['conflict_vehicle_motion_source_sha256']
                         if item.traffic_context == 'unresolved' else None})
        spec['files']['sidewalk-site.json'] = json.dumps(fixture_site) + '\n'
        spec['files']['sidewalk-history.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
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
