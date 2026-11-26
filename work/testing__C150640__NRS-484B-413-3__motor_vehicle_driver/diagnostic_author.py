"""Create tiny rear-signal synthetic compatibility fixtures, never original evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rear_signal import CASES

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def write(path, value):
    path.write_text(json.dumps(value, separators=(',', ':')) + '\n', encoding='utf-8')


def scene(case):
    value = {'cell_id': 'C150640', 'actor': 'motor_vehicle_driver',
             'route_xy': [[-20, 0], [-5, 0], [0, 0]],
             'stop_footprint_xy': [[0, -1], [4, -1], [4, 1], [0, 1]],
             'signal_light_name': 'RightBlinker',
             'rear_vehicle': {'driver_present': case.rear_driver,
                              'longitudinal_gap_m': 8, 'lateral_offset_m': .2,
                              'spawn_xy': [-8, .2]}}
    for name in ('jurisdiction', 'one_way_route', 'stop_footprint', 'ego_vehicle',
                 'ego_driver_control', 'signal_device', 'rear_visibility',
                 'conflict_context', 'official_direction_context'):
        value[name + '_source_sha256'] = 'synthetic-' + name
    for name in ('vehicle', 'driver', 'position', 'motion'):
        value['rear_vehicle'][name + '_source_sha256'] = 'synthetic-rear-' + name
    return value


def main():
    base = json.loads((REPO / 'runtime/fixtures/example.json').read_text())
    mapping = [json.loads(line) for line in base['files']['video_frames.jsonl'].splitlines() if line]
    for case in CASES:
        spec = json.loads(json.dumps(base))
        for unrelated in ('alley_context.json', 'body_history.jsonl', 'speed_samples.jsonl'):
            spec['files'].pop(unrelated, None)
        fixture_scene = scene(case)
        onset = 2 if case.signal_policy == 'before' else 6
        event = 4
        rows = []
        for i, frame in enumerate(mapping):
            rows.append({'original_frame': frame['carla_frame'], 'time_s': frame['time_s'],
                         'source_sha256': 'synthetic-diagnostic',
                         'ego_motion_source_sha256': 'synthetic-ego-motion',
                         'rear_motion_source_sha256': 'synthetic-rear-motion',
                         'signal_source_sha256': 'synthetic-signal',
                         'rear_visibility_source_sha256': 'synthetic-visibility',
                         'context_source_sha256': 'synthetic-context',
                         'route_source_sha256': fixture_scene['one_way_route_source_sha256'],
                         'ego_driver_in_control': True,
                         'rear_driver_present': case.rear_driver,
                         'ego_id': 'synthetic-ego', 'rear_id': 'synthetic-rear',
                         'rear_longitudinal_gap_m': 8, 'rear_lateral_offset_m': .2,
                         'ego_speed_mps': 8 if i < event else (0 if case.maneuver == 'stop' else 4),
                         'rear_speed_mps': 8,
                         'signal_displayed': i >= onset,
                         'signal_visible_from_rear': i >= onset,
                         'event_marker': case.maneuver if i == event else None})
        spec['files']['rear-signal-scene.json'] = json.dumps(fixture_scene) + '\n'
        spec['files']['rear-signal-history.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
        spec['files']['diagnostic-source-note.json'] = json.dumps({
            'source_kind': 'synthetic_diagnostic_fixture', 'accepted_original_source': False,
            'case_id': ROOT.name + '__' + case.case_id}) + '\n'
        output = ROOT / ('diagnostic-' + case.case_id + '.json')
        write(output, spec)
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json',
                               'source': str(output.relative_to(REPO)), 'sha256': digest}],
                  'generator': {'source': str(output.relative_to(REPO)), 'sha256': digest}}
        write(ROOT / ('diagnostic-' + case.case_id + '-recipe.json'), recipe)


if __name__ == '__main__':
    main()
