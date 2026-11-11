"""Saved-only right-half/closure observation from retained original sources."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from closure_source_audit import audit as audit_closure
from right_half_finalizer import analyze as analyze_right_half
from right_half_finalizer import build_result as build_right_half_result


CASE_ID = 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__right_half_closed'


def closure_construction(attempt):
    return audit_closure(attempt)


def analyze(attempt):
    report = analyze_right_half(attempt)
    if report['case_id'] != CASE_ID:
        raise ValueError('Wrong exact closure finalizer case')
    closure = closure_construction(attempt)
    report['measurements']['closure_construction'] = {
        'method': 'closure_construction',
        'value': {'cone_count': len(closure['cone_actor_ids']),
                  'authority_verified': False,
                  'frames': closure['frames']},
        'sources': {'closure_devices.jsonl': closure['closure_source_sha256'],
                    'directed_roadway_footprints.jsonl': closure['roadway_source_sha256']}}
    report['limitations'].append(
        'Cone occupancy is an engineering closure candidate; public authority and legal exception remain unverified.')
    return report


def build_result(attempt, report):
    root = Path(attempt)
    result = build_right_half_result(root, report)
    original = [json.loads(line) for line in (
        root / 'closure_devices.jsonl').read_text().splitlines() if line.strip()]
    channel = root / 'closure_cone_count.jsonl'
    if channel.exists():
        raise ValueError('Retain prior derived closure channel')
    channel.write_text(''.join(json.dumps({
        'frame': row['frame'], 'time_s': row['time_s'],
        'value': len(row['devices'])}) + '\n' for row in original))
    count = report['measurements']['closure_construction']['value']['cone_count']
    result['measured_values']['closure_construction'] = report[
        'measurements']['closure_construction']['value']
    result['recording_evidence'].append({
        'name': 'closure_cone_count', 'unit': 'count',
        'reference': 'closure_cone_count.jsonl',
        'sha256': sha256(channel.read_bytes()).hexdigest()})
    result['realized_observables']['closure_cone_count'] = {
        'unit': 'count', 'method': 'original Native cone actor IDs joined to roadway',
        'time_window': 'all original frames', 'statistic': 'min',
        'reference': 'closure_cone_count.jsonl', 'value': count,
        'sample_window_s': [original[0]['time_s'], original[-1]['time_s']]}
    result['target_checks'].append({
        'target': 'three right-half closure cone actors', 'requested': 3,
        'measured': count, 'method': 'original cone identity and right-half span',
        'tolerance': 0, 'matched': count == 3,
        'physical_cause_confirmed': False,
        'cause_evidence': 'Original cone transforms; public authority and physical review pending'})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior closure analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()
