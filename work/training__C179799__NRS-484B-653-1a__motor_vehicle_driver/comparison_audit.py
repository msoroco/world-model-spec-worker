"""Independent earlier/later roadside-worker response comparison audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ASSIGNMENT = 'training__C179799__NRS-484B-653-1a__motor_vehicle_driver'
PREFIX = ASSIGNMENT + '__selected_ce719cfa__'
COMPARISON = ASSIGNMENT + '__selected_ce719cfa__comparison'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison, left, right, output):
    require(comparison == COMPARISON, 'Unknown exact person-interaction comparison')
    left, right, output = Path(left), Path(right), Path(output)
    configs = [read(root/'config.json') for root in (left, right)]
    require([c['case_id'] for c in configs] == [PREFIX+'condition_a', PREFIX+'condition_b'],
            'Selected earlier/later case pair differs')
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s',
                'duration_frames', 'cameras', 'recording_description',
                'required_atoms', 'mandatory_channels'):
        require(configs[0].get(key) == configs[1].get(key),
                'Fixed construction/camera condition changed: '+key)
    require((configs[0]['interaction_mode'], configs[1]['interaction_mode']) ==
            ('earlier_response', 'later_response'),
            'Only declared response mode may vary')
    require(sha(left/'road.xodr') == sha(right/'road.xodr'),
            'Fixed paved-road geometry changed')
    packet = [read(root/'original-context-packet.json') for root in (left, right)]
    for item in packet:
        item.pop('case_id', None)
    require(packet[0] == packet[1],
            'Fixed public-access/worker/property/sight-line source changed')
    raw = [rows(root/'native-person-interaction.jsonl') for root in (left, right)]
    maps = [rows(root/'video_frames.jsonl') for root in (left, right)]
    require(all(len(stream) == 600 for stream in raw + maps),
            'Comparison needs 600 original joined frames each')
    differences = 0
    for index, (a, b, ma, mb) in enumerate(zip(raw[0], raw[1], maps[0], maps[1])):
        require(a['frame'] == b['frame'] == ma['video_frame'] == mb['video_frame'] == index and
                a['native_frame'] == ma['native_frame'] and
                b['native_frame'] == mb['native_frame'] and
                a['time_s'] == b['time_s'] and
                set(ma['camera_native_frames']) == set(mb['camera_native_frames']) == set(VIEWS),
                'Original response comparison frame/time/camera join differs')
        for key in ('person_x_m', 'person_y_m', 'person_vx_mps', 'person_vy_mps',
                    'person_radius_m', 'person_blueprint_id', 'ego_blueprint_id',
                    'ego_y_m', 'ego_radius_m'):
            require(a[key] == b[key], 'Fixed actor, road, or worker state changed: '+key)
        differences += int(a['ego_vx_mps'] != b['ego_vx_mps'])
    require(differences > 0, 'Response modes produced no observable driving difference')
    report = {'format': 'c179799-person-interaction-comparison-v1',
              'comparison_id': comparison, 'case_ids': [c['case_id'] for c in configs],
              'passed': True, 'different_speed_frames': differences,
              'checks': {'fixed_source_context': True, 'fixed_road': True,
                         'fixed_worker_and_vehicle_class': True,
                         'fixed_camera_duration_frame_join': True,
                         'declared_response_mode_only': True,
                         'observable_driving_difference': True},
              'diagnostic_fixture': all(read(root/'original-context-packet.json').get(
                  'synthetic_diagnostic') for root in (left, right)),
              'physical_or_legal_acceptance': False,
              'sources': [{name: sha(root/name) for name in (
                  'road.xodr', 'original-context-packet.json',
                  'native-person-interaction.jsonl', 'video_frames.jsonl')}
                  for root in (left, right)]}
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'comparison_id': comparison, 'passed': True,
                      'different_speed_frames': differences,
                      'diagnostic_fixture': report['diagnostic_fixture']}))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    audit(args.comparison, args.left, args.right, args.output)
