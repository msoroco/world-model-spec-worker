"""Independently check selected pair isolation in saved measurement reports.

This checks source binding and declared comparison variables. A diagnostic
fixture passes only a software check; physical outcomes remain unreviewed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from blind_encounter import audit_comparison

VARIABLES = {
    'stop_response': 'response',
    'precaution_before_proceeding': 'precaution',
    'approach_or_contact': 'encounter',
    'white_or_red_tip': 'cue',
    'white_cane_or_assistance': 'cue',
}


def _load(path: Path) -> tuple[dict, dict]:
    report = json.loads(path.read_text(encoding='utf-8'))
    if report.get('analysis_complete') is not True:
        raise ValueError('missing comparison evidence: analysis incomplete')
    measurements = report['measurements']
    root = path.parent
    for measurement in measurements.values():
        for name, expected in measurement['sources'].items():
            source = (root / name).resolve()
            if not source.is_relative_to(root.resolve()) or not source.is_file():
                raise ValueError('missing comparison source: ' + name)
            if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise ValueError('changed comparison source: ' + name)
    approach = measurements['approach_contact_measurement']['value']
    person = measurements['protected_person_measurement']
    history = root / 'original-history.jsonl'
    rows = [json.loads(line) for line in history.read_text().splitlines() if line]
    if not rows:
        raise ValueError('missing comparison history')
    value = {'case_id': report['case_id'].split('__')[-1],
             'person_actor_id': approach['person_actor_id'],
             'attestation_sha256': person['sources']['blindness-attestation.json'],
             'history_start_frame': rows[0]['frame'],
             'history_end_frame': rows[-1]['frame'],
             'source_sample_count': len(rows),
             'route_map_id': approach['route_map_id']}
    return value, report


def evaluate(plan_path: Path, comparison_id: str, left_path: Path,
             right_path: Path) -> dict:
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    rows = [row for row in plan['comparisons'] if row['comparison_id'] == comparison_id]
    if len(rows) != 1 or comparison_id not in VARIABLES:
        raise ValueError('undeclared comparison')
    row = rows[0]
    left, left_report = _load(left_path)
    right, right_report = _load(right_path)
    if [left_report['case_id'], right_report['case_id']] != row['case_ids']:
        raise ValueError('comparison case identity differs')
    for key in ('history_start_frame', 'history_end_frame', 'route_map_id'):
        if left[key] != right[key]:
            raise ValueError('fixed comparison condition changed: ' + key)
    result = audit_comparison(left, right, deliberate=VARIABLES[comparison_id])
    return {'format': 'worker-blind-person-comparison-audit',
            'comparison_id': comparison_id, 'case_ids': row['case_ids'],
            'passed': result['passed'], 'fixed_checks': result['fixed_checks'] +
            ['history_start_frame', 'history_end_frame', 'route_map_id'],
            'declared_difference': VARIABLES[comparison_id],
            'source_report_sha256': [hashlib.sha256(left_path.read_bytes()).hexdigest(),
                                     hashlib.sha256(right_path.read_bytes()).hexdigest()],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.plan, args.comparison, args.left, args.right), sort_keys=True))


if __name__ == '__main__':
    main()
