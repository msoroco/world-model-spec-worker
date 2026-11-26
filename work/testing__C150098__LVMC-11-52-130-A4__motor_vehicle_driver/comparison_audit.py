"""Audit four exact original hydrant comparisons from independent case audits."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from hydrant import ASSIGNMENT

HERE = Path(__file__).resolve().parent


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit_comparison(comparison_id, audit_paths):
    plan = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))
    rows = [row for row in plan['comparisons'] if row['comparison_id'] == comparison_id]
    require(len(rows) == 1, 'unknown exact hydrant comparison')
    expected = rows[0]['case_ids']
    require(set(audit_paths) == set(expected) and len(audit_paths) == len(expected),
            'comparison must include every exact case once')
    audits, sources = [], {}
    for case_id in expected:
        path = Path(audit_paths[case_id])
        require(path.is_file() and not path.is_symlink(), 'original case audit missing')
        item = json.loads(path.read_text(encoding='utf-8'))
        require(item.get('format') == 'c150098-original-delivery-audit-v1' and
                item.get('case_id') == case_id and
                item.get('original_frame_count') == 900 and
                item.get('legal_status') == 'unresolved' and
                item.get('source_sha256', {}).get('capture-seal.json'),
                'source-bound original case audit required')
        audits.append(item)
        sources[case_id] = hashlib.sha256(path.read_bytes()).hexdigest()
    for key in ('map_sha256', 'hydrant_identity_sha256',
                'parallel_parking_authority_sha256'):
        require(len({item[key] for item in audits}) == 1,
                'fixed physical hydrant or parking authority changed: ' + key)
    if comparison_id.endswith('boundary'):
        require([item['side'] for item in audits] ==
                (['upstream'] if comparison_id.startswith('upstream') else ['downstream']) * 3,
                'boundary side differs')
        require(all(item['activity'] == 'park' and item['exception_kind'] == 'none'
                    for item in audits), 'boundary activity differs')
        values = [item['minimum_target_side_gap_m'] for item in audits]
        require(values[0] < values[1] < values[2],
                'original measured below/at/above ordering missing')
    elif comparison_id == 'stop_stand_park_activity':
        require([item['activity'] for item in audits] == ['park', 'stop', 'stand'],
                'original stop/stand/park activities missing')
        require(len({item['side'] for item in audits}) == 1 and
                all(item['exception_kind'] == 'none' for item in audits),
                'activity comparison fixed conditions changed')
    elif comparison_id == 'lawful_exception_sources':
        require(all(item['activity'] == 'stop' and item['side'] == 'upstream'
                    for item in audits), 'exception fixed activity or side changed')
        require([item['exception_kind'] for item in audits] ==
                ['none', 'lawful_traffic_conflict', 'police_direction',
                 'traffic_device_direction'], 'exact exception source set missing')
    else:
        raise ValueError('unknown comparison')
    return {'format': 'c150098-original-comparison-audit-v1',
        'assignment_id': ASSIGNMENT, 'comparison_id': comparison_id,
        'case_ids': expected, 'case_audit_sha256': sources,
        'measured_gaps_m': {item['case_id']: item['minimum_target_side_gap_m']
                            for item in audits},
        'fixed_source_sha256': {key: audits[0][key] for key in
            ('map_sha256', 'hydrant_identity_sha256',
             'parallel_parking_authority_sha256')},
        'legal_distance_convention': 'unresolved_review',
        'exception_necessity': 'requires_independent_review',
        'legal_status': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--audit', action='append', nargs=2,
                        metavar=('CASE_ID', 'PATH'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior hydrant comparison audit')
    pairs = dict(args.audit)
    require(len(pairs) == len(args.audit), 'duplicate case audit')
    args.output.write_text(json.dumps(audit_comparison(args.comparison, pairs),
                                      indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
