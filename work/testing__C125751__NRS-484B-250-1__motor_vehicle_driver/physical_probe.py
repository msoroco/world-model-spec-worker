"""Exercise complete, incomplete and missing crossing evidence on CPU fixtures.

These outputs are synthetic test results. They never certify a Native recording.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_signal_audit import audit


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def fixture_result(case: str, status: str, history_hash: str, complete: dict) -> dict:
    return {
        'case_id': case,
        'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True,
        'maneuver_completed': status == 'met',
        'realized_observables': complete if status == 'met' else {},
        'physical_checks': {'maneuver': {
            'status': status,
            'method': 'sealed synthetic body-outline crossing entry and clearance',
            'sources': {'signal-history.json': history_hash},
        }},
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
    }


def run(case: str, attempt: Path, output: Path) -> dict:
    attempt = attempt.resolve()
    output = output.resolve()
    if not attempt.is_dir() or output.exists():
        raise ValueError('Use an existing diagnostic attempt and a fresh output directory')
    output.mkdir(parents=True)
    source = json.loads((attempt / 'acquisition-provenance.json').read_text())
    if source.get('provenance_kind') != 'synthetic_fixture' or source.get('diagnostic_fixture') is not True:
        raise ValueError('Physical CPU probe requires explicit synthetic provenance')
    result = json.loads((attempt / 'result.json').read_text())
    if result.get('case_id') != case or result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
        raise ValueError('Complete saved diagnostic result absent')
    if not result.get('realized_observables'):
        raise ValueError('Complete saved result omitted measured observables')
    original = (attempt / 'signal-history.json').read_bytes()
    history = json.loads(original)
    packet = json.loads((attempt / 'signal-packet.json').read_text())
    review_sha = sha((attempt / 'review.json').read_bytes())
    audit(packet, original, case, review_sha)
    rows = history['frames']
    incomplete = json.loads(original)
    # Keep the final ego outline over the crossing instead of clearing it.
    inside = incomplete['frames'][-2]['ego']['body_vertices_xy_m']
    incomplete['frames'][-1]['ego']['body_vertices_xy_m'] = inside
    incomplete['frames'][-1]['ego']['xy_m'] = incomplete['frames'][-2]['ego']['xy_m']
    missing = json.loads(original)
    missing['frames'][1]['ego'].pop('body_vertices_xy_m')
    variants = (
        ('complete_motion', original, 'met', None),
        ('incomplete_motion', json.dumps(incomplete).encode(), 'not_met',
         'crossing entry and clearance unobserved'),
        ('missing_evidence', json.dumps(missing).encode(), 'unverified',
         'Native body outline absent'),
    )
    for kind, payload, status, expected in variants:
        (output / (kind + '-history.json')).write_bytes(payload)
        if expected:
            changed = dict(packet, payload_sha256=sha(payload))
            try:
                audit(changed, payload, case, review_sha)
            except ValueError as error:
                if expected not in str(error):
                    raise
            else:
                raise ValueError('Changed diagnostic history was accepted: ' + kind)
        write(output / (kind + '-result.json'), fixture_result(
            case, status, sha(payload), result['realized_observables']))
    return {'case_id': case, 'diagnostic_fixture': True,
            'statuses': {'complete_motion': 'met',
                         'incomplete_motion': 'not_met',
                         'missing_evidence': 'unverified'},
            'lifecycle': ['capture_finished', 'encoders_closed',
                          'restoration_verified', 'native_exit',
                          'owner_released', 'saved_processing_started'],
            'physical_acceptance_claimed': False,
            'rows': len(rows)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.attempt, args.output), indent=2))
