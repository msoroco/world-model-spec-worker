"""Audit two controlled C24751 comparisons from independent original case audits."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from flashing_red_native import ASSIGNMENT

HERE = Path(__file__).resolve().parent


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_comparison(comparison_id, audit_paths):
    plan = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))
    matches = [row for row in plan['comparisons'] if row['comparison_id'] == comparison_id]
    require(len(matches) == 1, 'unknown exact flashing-red comparison')
    expected = matches[0]['case_ids']
    require(set(audit_paths) == set(expected) and len(audit_paths) == len(expected),
            'comparison must include every exact case once')
    audits, sources = [], {}
    for case_id in expected:
        path = Path(audit_paths[case_id])
        require(path.is_file() and not path.is_symlink(), 'original case audit missing')
        item = json.loads(path.read_text(encoding='utf-8'))
        require(item.get('format') == 'c24751-original-delivery-audit-v1'
                and item.get('case_id') == case_id
                and item.get('original_frame_count') == 900
                and item.get('flashing_red_transitions', 0) >= 2
                and item.get('legal_status') == 'unresolved'
                and item.get('post_stop_right_to_proceed') == 'unresolved_applicable_rules'
                and item.get('source_sha256', {}).get('capture-seal.json'),
                'source-bound original case audit required')
        audits.append(item)
        sources[case_id] = hashlib.sha256(path.read_bytes()).hexdigest()
    for key in ('map_sha256', 'signal_identity_sha256', 'occluder_identity_sha256'):
        require(len({item[key] for item in audits}) == 1,
                'fixed physical signal/occluder source changed: ' + key)
    if comparison_id == 'crosswalk_stop_location':
        require([item['reference_kind'] for item in audits] == ['crosswalk', 'crosswalk']
                and len({item['stop_geometry_sha256'] for item in audits}) == 1
                and len({item['surveyed_reference_m'] for item in audits}) == 1,
                'crosswalk stop-location fixed geometry changed')
        first = [row['front_m'] for row in audits[0]['stop_observations']]
        second = [row['front_m'] for row in audits[1]['stop_observations']]
        require(first and second and min(first) < min(second),
                'original measured early/late front order missing')
    elif comparison_id == 'statutory_reference_alternatives':
        require([item['reference_kind'] for item in audits] ==
                ['crosswalk', 'limit_line', 'intersection'],
                'statutory stop-reference alternatives missing')
        require(all(item['stop_observations'] for item in audits),
                'original complete cessation missing for alternative')
    else:
        raise ValueError('unknown comparison')
    return {'format': 'c24751-original-comparison-audit-v1',
        'assignment_id': ASSIGNMENT, 'comparison_id': comparison_id,
        'case_ids': expected, 'case_audit_sha256': sources,
        'measured_front_at_stop_m': {item['case_id']: item['stop_observations'][0]['front_m']
                                      for item in audits},
        'fixed_source_sha256': {key: audits[0][key] for key in
            ('map_sha256', 'signal_identity_sha256', 'occluder_identity_sha256')},
        'post_stop_right_to_proceed': 'unresolved_applicable_rules',
        'legal_status': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--audit', action='append', nargs=2,
                        metavar=('CASE_ID', 'PATH'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior flashing-red comparison audit')
    pairs = dict(args.audit)
    require(len(pairs) == len(args.audit), 'duplicate case audit')
    args.output.write_text(json.dumps(audit_comparison(args.comparison, pairs),
                                      indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
