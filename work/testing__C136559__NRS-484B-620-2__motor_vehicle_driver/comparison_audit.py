"""Independent paired original-source audit for five signed-zone comparisons."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit as audit_delivery, sha
from speed_zone import audit_pair

DELIBERATE = {
    'speed_below_above': {'requested_mph'},
    'speed_near_above': {'requested_mph'},
    'zone_occupancy': {'zone_mode'},
    'sign_installation': {'zone_mode'},
    'directional_sign': {'direction'},
}


def source(attempt, case_id):
    attempt = Path(attempt).resolve()
    custody = audit_delivery(attempt, case_id)
    config = json.loads((attempt / 'config.json').read_text())
    capture = json.loads((attempt / 'original-attempt/capture.json').read_text())
    site = json.loads((attempt / 'original-attempt/site-packet.json').read_text())['site']
    variables = config['case']['draft_variables']
    # Original weather requires a source hash. The explicit diagnostic sentinel
    # exercises software joins without claiming a physical fixed condition.
    weather = capture.get('weather_sha256')
    if not weather and not custody['diagnostic_fixture']:
        raise ValueError('original comparison weather source missing')
    return {'case_id': case_id, 'road_source_sha256': site['road_source_sha256'],
            'map_source_sha256': capture['map_source_sha256'],
            'zone_establishment_source_sha256': capture['zone_establishment_source_sha256'],
            'zone_extent_source_sha256': capture['zone_extent_source_sha256'],
            'sign_instruction_source_sha256': capture['sign_instruction_source_sha256'],
            'ego_blueprint': capture['ego_blueprint'],
            'weather_sha256': weather or 'diagnostic_weather_unverified',
            'camera_plan_sha256': capture['camera_plan_sha256'],
            'duration_frames': config['frame_count'],
            'requested_mph': variables['requested_mph'],
            'zone_mode': variables['zone_mode'], 'direction': variables['direction'],
            'original_history_sha256': sha(attempt / 'original-attempt/capture.json'),
            'inside_zone_history': [r['inside_zone'] for r in capture['original_rows']],
            'sign_installed_history': [r['sign_installed'] for r in capture['original_rows']],
            'actual_speed_mps_history': [r['actual_speed_mps'] for r in capture['original_rows']],
            'diagnostic_fixture': custody['diagnostic_fixture'],
            'source_custody': custody}


def audit(comparison_id, left_attempt, left_case, right_attempt, right_case,
          allow_diagnostic=False):
    if comparison_id not in DELIBERATE:
        raise ValueError('unknown exact speed comparison')
    left = source(left_attempt, left_case)
    right = source(right_attempt, right_case)
    if (left['diagnostic_fixture'] or right['diagnostic_fixture']) and not allow_diagnostic:
        raise ValueError('synthetic paired sources cannot satisfy original comparison')
    audit_pair(left, right, DELIBERATE[comparison_id])
    if comparison_id == 'zone_occupancy' and \
            left['inside_zone_history'] == right['inside_zone_history']:
        raise ValueError('original zone occupancy difference absent')
    if comparison_id == 'sign_installation' and \
            left['sign_installed_history'] == right['sign_installed_history']:
        raise ValueError('original sign installation difference absent')
    if comparison_id in ('speed_below_above', 'speed_near_above') and \
            left['actual_speed_mps_history'] == right['actual_speed_mps_history']:
        raise ValueError('original speed history difference absent')
    return {'format': 'worker-speed-original-comparison-audit',
            'comparison_id': comparison_id, 'case_ids': [left_case, right_case],
            'deliberate_differences': sorted(DELIBERATE[comparison_id]),
            'original_source_sha256': [left['original_history_sha256'],
                                       right['original_history_sha256']],
            'diagnostic_fixture': left['diagnostic_fixture'] or right['diagnostic_fixture'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left-attempt', type=Path, required=True)
    parser.add_argument('--left-case', required=True)
    parser.add_argument('--right-attempt', type=Path, required=True)
    parser.add_argument('--right-case', required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.left_attempt, args.left_case,
                           args.right_attempt, args.right_case,
                           args.allow_diagnostic), sort_keys=True))
