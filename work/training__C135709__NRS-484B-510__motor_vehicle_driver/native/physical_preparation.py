"""Source-bound CPU diagnostic of requested stop/stand/park motion.

This script evaluates only synthetic fixture actor bodies. It does not verify
actual Native motion, restricted-zone authority, participant purpose or law.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_capture_closure(capture):
    if (capture.get('closed') is not True or
            capture.get('world_restored') is not True or
            capture.get('frame_count') != 600):
        raise ValueError('Diagnostic capture lifecycle incomplete')


def evaluate(case, kind):
    if kind not in KINDS or case not in ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2', 'stop_only', 'stand_only'):
        raise ValueError('Unsupported physical diagnostic')
    source = ROOT / 'selected-source' / case
    actor = source / 'actor-frames.jsonl'
    zone = source / 'zone-survey.json'
    capture = source / 'capture-manifest.json'
    validate_capture_closure(json.loads(capture.read_text()))
    bounds = json.loads(zone.read_text())['bounds_m']
    rows = [json.loads(line) for line in actor.read_text().splitlines()]
    if len(rows) != 600 or any(r['frame'] != i for i, r in enumerate(rows)):
        raise ValueError('Diagnostic fixture lacks exact 600-frame source')
    if kind == 'incomplete_motion':
        rows = [dict(row, ego_body_m=[100.0, 100.0, 104.0, 102.0]) for row in rows]
    if kind == 'missing_evidence':
        rows = []
    settled = [r for r in rows if r['ego_speed_mps'] <= 0.1 and r['ego_body_m'][0] >= bounds[0] and r['ego_body_m'][1] >= bounds[1] and r['ego_body_m'][2] <= bounds[2] and r['ego_body_m'][3] <= bounds[3]]
    requested = [r for r in rows if r.get('departure_requested')]
    moved_after = [r for r in requested if r['ego_speed_mps'] > 0.1]
    departure_case = case in ('stop_only', 'stand_only')
    complete = bool(settled) and (not departure_case or bool(moved_after))
    status = 'unverified' if kind == 'missing_evidence' else 'met' if complete else 'not_met'
    if kind == 'complete_motion' and status != 'met':
        raise ValueError('Selected diagnostic did not realize requested maneuver')
    if kind == 'incomplete_motion' and status != 'not_met':
        raise ValueError('Altered diagnostic did not fail maneuver')
    return {
        'format': 'c135709-physical-diagnostic-v1',
        'case_id': ROOT.name + '__' + case,
        'kind': kind,
        'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True,
        'original_native_observed': False,
        'legal_verdict': None,
        'fixture_perturbation': ('none' if kind == 'complete_motion' else
                                 'in-memory ego body moved outside zone' if kind == 'incomplete_motion' else
                                 'in-memory actor rows omitted'),
        'maneuver_completed': complete,
        'physical_checks': {'maneuver': {
            'status': status,
            'method': 'Recompute full ego footprint inside surveyed zone at rest; stop/stand also require measured motion after departure request. Altered and missing source fixtures are tested separately.',
            'sources': [
                {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}
                for path in (actor, zone, capture)
            ],
            'limitations': ['Synthetic body and map fixture only', 'No Native physical motion, sign authority, actual loading, purpose, interference or legal outcome established'],
        }},
        'realized_observables': {'stopped_in_zone_frames': len(settled), 'departure_requested_frames': len(requested), 'moving_after_departure_request_frames': len(moved_after)} if complete else {},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=KINDS, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = evaluate(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'kind': args.kind, 'status': result['physical_checks']['maneuver']['status']}))


if __name__ == '__main__':
    main()
