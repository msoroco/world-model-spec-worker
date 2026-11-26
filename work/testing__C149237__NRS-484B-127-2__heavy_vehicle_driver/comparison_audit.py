"""Audit seven exact controlled comparisons from independent original audits."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from truck_following import audit_comparison as compare_pair
from native_packet import AID

HERE = Path(__file__).resolve().parent
VARIED = {
    'passing_permission': 'subject_pass_completed',
    'entering_vehicle': 'entered_gap_distinct_vehicle_count',
    'multilane_exception': 'same_direction_available_lane_count_min',
    'lead_width_qualification': 'lead_width_min_m',
    'subject_width_qualification': 'subject_width_min_m',
}
FIXED = {
    'passing_permission': ('subject_width_min_m', 'lead_width_min_m',
                           'same_direction_available_lane_count_min'),
    'entering_vehicle': ('subject_width_min_m', 'lead_width_min_m',
                         'same_direction_available_lane_count_min'),
    'multilane_exception': ('subject_width_min_m', 'lead_width_min_m'),
    'lead_width_qualification': ('subject_width_min_m', 'same_direction_available_lane_count_min'),
    'subject_width_qualification': ('lead_width_min_m', 'same_direction_available_lane_count_min'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_comparison(comparison_id, audit_paths):
    plan = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))
    matches = [row for row in plan['comparisons'] if row['comparison_id'] == comparison_id]
    require(len(matches) == 1, 'unknown exact truck comparison')
    expected = matches[0]['case_ids']
    require(set(audit_paths) == set(expected) and len(audit_paths) == len(expected),
            'comparison must include every exact case once')
    audits, sources = [], {}
    for case_id in expected:
        path = Path(audit_paths[case_id])
        require(path.is_file() and not path.is_symlink(), 'original case audit missing')
        item = json.loads(path.read_text(encoding='utf-8'))
        measured = item.get('measurement', {})
        require(item.get('format') == 'c149237-original-delivery-audit-v1'
                and item.get('case_id') == case_id
                and item.get('original_frame_count') == 900
                and measured.get('original_frame_count') == 900
                and measured.get('legal_judgment') == 'unresolved'
                and item.get('legal_status') == 'unresolved'
                and item.get('source_sha256', {}).get('capture-seal.json')
                and item.get('original_context', {}).get('road_source_sha256'),
                'source-bound original truck case audit required')
        audits.append(item)
        sources[case_id] = hashlib.sha256(path.read_bytes()).hexdigest()
    for key in ('road_source_sha256', 'route_geometry_sha256', 'weather_sha256'):
        require(len({item['original_context'][key] for item in audits}) == 1,
                'fixed original road or weather source changed: ' + key)
    values = [dict(item['measurement'], case_id=item['case_id']) for item in audits]
    if comparison_id == '500ft_space_below_at_above':
        require(len(values) == 3 and all(value['subject_width_min_m'] == values[0]['subject_width_min_m']
                and value['lead_width_min_m'] == values[0]['lead_width_min_m']
                and value['same_direction_available_lane_count_min'] == values[0]['same_direction_available_lane_count_min']
                for value in values), '500-foot fixed truck context changed')
        gaps = [value['steady_gap_min_m'] for value in values]
        require(gaps[0] < gaps[1] < gaps[2], 'original below/at/above body gap order missing')
        pair_proof = {'ordered_gap_m': gaps}
    elif comparison_id in VARIED:
        pair_proof = compare_pair(values[0], values[1],
                                  fixed_fields=FIXED[comparison_id],
                                  varied_field=VARIED[comparison_id])
        if comparison_id == 'passing_permission':
            require(values[1]['subject_pass_completed'] is True
                    and values[1]['subject_pass_geometry_verified'] is True,
                    'original whole-body passing completion missing')
    elif comparison_id == 'conditions_permit':
        pair_proof = compare_pair(values[0], values[1],
                                  fixed_fields=('subject_width_min_m', 'lead_width_min_m',
                                                'same_direction_available_lane_count_min',
                                                'steady_gap_min_m'),
                                  varied_field='original_source_sha256')
        contexts = [item['original_context']['condition_context'] for item in audits]
        require(contexts[0] != contexts[1], 'original conditions context did not vary')
        pair_proof['observed_condition_contexts'] = contexts
    else:
        raise ValueError('unknown exact truck comparison')
    return {'format': 'c149237-original-comparison-audit-v1',
        'assignment_id': AID, 'comparison_id': comparison_id,
        'case_ids': expected, 'case_audit_sha256': sources,
        'comparison_proof': pair_proof,
        'fixed_road_source_sha256': audits[0]['original_context']['road_source_sha256'],
        'conditions_permit': 'unresolved', 'entry_without_danger': 'unresolved',
        'legal_status': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--audit', action='append', nargs=2,
                        metavar=('CASE_ID', 'PATH'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior truck comparison audit')
    pairs = dict(args.audit)
    require(len(pairs) == len(args.audit), 'duplicate case audit')
    args.output.write_text(json.dumps(audit_comparison(args.comparison, pairs),
                                      indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
