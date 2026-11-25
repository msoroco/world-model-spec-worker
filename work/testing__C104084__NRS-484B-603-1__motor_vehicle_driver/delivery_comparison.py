"""Compare two separately audited original crest deliveries.

Identical site/map/limit/route sources are fixed; observed Native actor IDs and
camera bytes are expected to differ between independent captures. The measured
speed profile is the comparison variable, never a legal verdict.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from saved_crest_audit import ASSIGNMENT
from saved_delivery_audit import audit as audit_delivery

COMPARISONS = {
    'early_vs_late_precrest_decrease': ('early_decrease', 'late_decrease'),
    'decrease_vs_steady_approach': ('early_decrease', 'steady_approach'),
}


def compare(left_attempt, right_attempt, comparison_id):
    if comparison_id not in COMPARISONS:
        raise ValueError('exact selected crest comparison required')
    left_profile, right_profile = COMPARISONS[comparison_id]
    roots = (Path(left_attempt), Path(right_attempt))
    cases = tuple(ASSIGNMENT + '__' + profile for profile in (left_profile, right_profile))
    proofs = [audit_delivery(root, expected_case=case)
              for root, case in zip(roots, cases)]
    manifests = [json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
                 for root in roots]
    finalized = [json.loads((root / 'finalized.json').read_text(encoding='utf-8'))
                 for root in roots]
    if manifests[0]['native_capture_ref'] == manifests[1]['native_capture_ref']:
        raise ValueError('two distinct original Native capture references required')
    for key in ('native_map_sha256', 'grade_source', 'other_route_source',
                'prescribed_limit_source'):
        a, b = manifests[0][key], manifests[1][key]
        if isinstance(a, dict):
            a, b = a['sha256'], b['sha256']
        if a != b:
            raise ValueError('fixed original crest source differs: ' + key)
    for key in ('duration_s', 'rate_hz', 'camera_dimensions', 'approach_start_m'):
        if manifests[0][key] != manifests[1][key]:
            raise ValueError('fixed original capture contract differs: ' + key)
    contexts = [json.loads((root / manifest['context_source']['path']).read_text(encoding='utf-8'))
                for root, manifest in zip(roots, manifests)]
    for key in ('road_id', 'highway_status', 'highway_source_ref',
                'prescribed_limit_mps', 'limit_source_ref'):
        if contexts[0].get(key) != contexts[1].get(key):
            raise ValueError('fixed original road and limit context differs: ' + key)
    motion = [json.loads((root / manifest['motion_source']['path']).read_text(encoding='utf-8'))
              for root, manifest in zip(roots, manifests)]
    if any(abs(a['time_s'] - b['time_s']) > 1e-6 or
           abs(a['other_s_m'] - b['other_s_m']) > 1.0
           for a, b in zip(motion[0], motion[1])):
        raise ValueError('fixed observed opposing-vehicle motion differs beyond engineering band')
    def initial_speed(rows, start, crest):
        return next(row['ego_speed_mps'] for row in rows
                    if start <= row['ego_s_m'] < crest)
    crest = finalized[0]['crest_crossing']['crest_station_m']
    speeds = [initial_speed(rows, manifest['approach_start_m'], crest)
              for rows, manifest in zip(motion, manifests)]
    if abs(speeds[0] - speeds[1]) > 0.5:
        raise ValueError('fixed measured approach speed differs beyond engineering band')
    measurements = [value['speed_profile_witness'] for value in finalized]
    if [m['profile'] for m in measurements] != [left_profile, right_profile]:
        raise ValueError('original measured profile witnesses differ from selected cases')
    if (measurements[0]['first_speed_decrease_station_m'] ==
            measurements[1]['first_speed_decrease_station_m'] and
            measurements[0]['precrest_speed_change_mps'] ==
            measurements[1]['precrest_speed_change_mps']):
        raise ValueError('selected speed-profile difference was not measured')
    return {'format': 'c104084-original-delivery-comparison-v1',
            'assignment_id': ASSIGNMENT, 'comparison_id': comparison_id,
            'case_ids': list(cases),
            'source_manifest_sha256': [proof['source_manifest_sha256'] for proof in proofs],
            'original_capture_refs': [m['native_capture_ref'] for m in manifests],
            'fixed_source_sha256': {
                key: manifests[0][key]['sha256'] for key in
                ('grade_source', 'other_route_source', 'prescribed_limit_source')},
            'measured_profiles': measurements,
            'physical_acceptance': False, 'legal_judgment': 'unresolved'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--left-attempt', required=True)
    parser.add_argument('--right-attempt', required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    result = compare(args.left_attempt, args.right_attempt, args.comparison)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
