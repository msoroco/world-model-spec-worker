"""Create case-specific synthetic compatibility sources, never original evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from zone_motion import CASES, intersection_area

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, separators=(',', ':'), ensure_ascii=False) + '\n', encoding='utf-8')


def scene(case) -> dict:
    zone = [0.0, 0.0, 10.0, 2.0]
    y = 5.0 if case.route == 'beside' else 1.0
    start = [-10.0, y]
    end = [5.0 if case.route == 'within' else 20.0, y]
    result = {
        'cell_id': 'C412974', 'actor': 'motor_vehicle_driver',
        'driver_present': True, 'motor_vehicle': True,
        'highway_public_access': True, 'highway_dedicated_public_authority': True,
        'zone_designation_status': case.designation,
        'official_pedestrian_exclusive': True if case.designation == 'active' else None,
        'marking_or_sign_visible': True if case.designation == 'active' else None,
        'designation_interval_s': [0, 45] if case.designation == 'active' else None,
        'route_variant': case.route, 'zone_rect_m': zone,
        'vehicle_start_xy': start, 'vehicle_target_xy': end,
        'vehicle_route_xy': [start, [5.0, y], end],
        'highway_status': 'synthetic', 'official_designation': 'synthetic',
        'visible_marking': 'synthetic', 'zone_boundary': 'synthetic',
        'driver_identity': 'synthetic', 'vehicle_class': 'synthetic',
    }
    for name in ('map', 'highway', 'zone_boundary', 'designation', 'marking',
                 'vehicle', 'driver', 'route'):
        result[name + '_source_sha256'] = 'synthetic-' + name
    return result


def main() -> None:
    base = json.loads((REPO / 'runtime/fixtures/example.json').read_text(encoding='utf-8'))
    mapping = [json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines()]
    for case in CASES:
        spec = json.loads(json.dumps(base))
        for name in ('alley_context.json', 'body_history.jsonl', 'speed_samples.jsonl'):
            spec['files'].pop(name, None)
        data = scene(case)
        xs = [-10.0, 5.0, data['vehicle_target_xy'][0]]
        ys = [data['vehicle_start_xy'][1]] * 3
        history = []
        for index, row in enumerate(mapping):
            x, y = xs[min(index, 2)], ys[min(index, 2)]
            body = [x - .5, y - .4, x + .5, y + .4]
            item = {
                'original_frame': row['carla_frame'], 'time_s': row['time_s'],
                'vehicle_id': 'synthetic-ego', 'vehicle_body_rect_m': body,
                'vehicle_speed_mps': 4.0,
                'zone_overlap_area_m2': intersection_area(body, data['zone_rect_m']),
            }
            for name in ('frame', 'vehicle_body', 'vehicle_motion', 'zone_boundary',
                         'designation', 'marking_visibility'):
                item[name + '_source_sha256'] = data.get(name + '_source_sha256', 'synthetic-' + name)
            history.append(item)
        spec['files']['safety-zone-site.json'] = json.dumps({'scene': data}) + '\n'
        spec['files']['safety-zone-history.jsonl'] = ''.join(json.dumps(row) + '\n' for row in history)
        spec['files']['diagnostic-source-note.json'] = json.dumps({
            'source_kind': 'synthetic_diagnostic_fixture', 'accepted_original_source': False,
            'case_id': ROOT.name + '__' + case.name}) + '\n'
        spec['files']['carla_recorder.log'] = 'synthetic diagnostic recorder placeholder\n'
        source = ROOT / ('diagnostic-' + case.name + '.json')
        write(source, spec)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        name = str(source.relative_to(REPO))
        recipe = {
            'format': 'worker-fixture-recipe',
            'sources': [{'path': 'diagnostic-input.json', 'source': name, 'sha256': digest}],
            'generator': {'source': name, 'sha256': digest},
        }
        write(ROOT / ('diagnostic-' + case.name + '-recipe.json'), recipe)


if __name__ == '__main__':
    main()
