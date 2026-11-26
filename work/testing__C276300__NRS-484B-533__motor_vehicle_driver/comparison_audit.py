"""Independently check six source-bound controlled grade-standing contrasts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit as audit_delivery

AXES = {
    'engine_off_vs_on': {'engine_off_request'},
    'brake_set_vs_off': {'brake_set_request'},
    'wheels_toward_vs_away': {'wheels_toward_request'},
    'depart_vs_stay': {'person_action', 'engine_off_request',
                       'brake_set_request', 'wheels_toward_request'},
    'depart_vs_passenger': {'person_action'},
    'slope_vs_flat': {'grade_kind', 'grade_percent'},
}
SOURCE_VARIANTS = {'engine_off_request': 'engine_source_sha256',
                   'brake_set_request': 'brake_mechanics_source_sha256',
                   'wheels_toward_request': 'front_wheels_source_sha256',
                   'person_action': 'person_actions_source_sha256',
                   'grade_kind': 'grade_source_sha256',
                   'grade_percent': 'grade_source_sha256'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(plan_path, attempts, *, diagnostic_fixture=False, comparison_id=None):
    plan = json.loads(Path(plan_path).read_text())
    if set(AXES) != {row['comparison_id'] for row in plan['comparisons']}:
        raise ValueError('six exact comparisons required')
    if comparison_id is not None and comparison_id not in AXES:
        raise ValueError('unknown exact comparison')
    observed = []
    for comparison in plan['comparisons']:
        ident = comparison['comparison_id']
        if comparison_id is not None and ident != comparison_id:
            continue
        case_ids = comparison['case_ids']
        if len(case_ids) != 2 or any(case not in attempts for case in case_ids):
            raise ValueError('comparison source attempt missing: ' + ident)
        packets, ticks, receipts = [], [], []
        for case in case_ids:
            root = Path(attempts[case])
            receipt = audit_delivery(case, root, plan_path)
            if receipt['diagnostic_fixture'] != diagnostic_fixture:
                raise ValueError('comparison source kind differs')
            packets.append(json.loads((root / ('reviewed-packet.json' if
                diagnostic_fixture else 'source-packet.json')).read_text())['scene'])
            ticks.append([json.loads(line) for line in (root / 'original-ticks.jsonl').read_text().splitlines()])
            receipts.append(receipt)
        left, right = packets
        allowed = AXES[ident] | {SOURCE_VARIANTS[key] for key in AXES[ident]}
        if diagnostic_fixture:
            allowed |= {key for key in left if key.endswith('_source_sha256')}
        allowed |= {'case_id'}
        if set(left) != set(right) or any(left[key] != right[key] for key in left if key not in allowed):
            raise ValueError('comparison changed fixed original scene source: ' + ident)
        if not any(left[key] != right[key] for key in AXES[ident]):
            raise ValueError('declared comparison axis did not change: ' + ident)
        if len(ticks[0]) != len(ticks[1]) or any(
                a['original_frame'] != b['original_frame'] or a['time_s'] != b['time_s']
                for a, b in zip(*ticks)):
            raise ValueError('comparison original frame/time alignment differs: ' + ident)
        observed.append({'comparison_id': ident, 'case_ids': case_ids,
                         'changed_axes': sorted(AXES[ident]),
                         'fixed_scene_parameters': True,
                         'fixed_source_hashes': not diagnostic_fixture,
                         'frame_time_aligned': True,
                         'source_receipt_sha256': [hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest() for r in receipts],
                         'status': 'synthetic_software_only' if diagnostic_fixture else
                                   'original_measurements_pending_judgment'})
    return {'format': 'c276300-comparison-audit-v1',
            'assignment_id': plan['assignment_id'], 'plan_sha256': sha(plan_path),
            'diagnostic_fixture': diagnostic_fixture, 'comparisons': observed,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--attempts', type=Path)
    parser.add_argument('--comparison-id')
    parser.add_argument('--attempt', action='append', type=Path)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior comparison audit')
    if args.attempts is not None:
        attempts = json.loads(args.attempts.read_text())
    elif args.comparison_id and args.attempt and len(args.attempt) == 2:
        plan = json.loads(args.plan.read_text())
        pair = next((row['case_ids'] for row in plan['comparisons']
                     if row['comparison_id'] == args.comparison_id), None)
        if pair is None:
            raise ValueError('unknown exact comparison')
        attempts = dict(zip(pair, map(str, args.attempt)))
    else:
        raise ValueError('supply exact attempts or two ordered attempts')
    result = audit(args.plan, attempts, diagnostic_fixture=args.diagnostic_fixture,
                   comparison_id=args.comparison_id)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(len(result['comparisons']))
