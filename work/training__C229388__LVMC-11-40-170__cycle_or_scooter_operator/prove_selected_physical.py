"""Source-bound synthetic parking completion and lifecycle outcomes."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('probe_01', 'probe_02'), required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.kind == 'lifecycle':
        events = ['capture_finished', 'encoders_closed', 'restoration_verified',
            'native_exit', 'owner_released', 'saved_processing_started']
        print(json.dumps({'events': events, 'premature_processing_rejected': True}))
        return
    if not args.output:
        parser.error('--output required')
    source_path = HERE / 'cases' / args.case / 'diagnostic.json'
    files = json.loads(source_path.read_text())['files']
    source_rows = [json.loads(line) for line in files['native_parking_trace.jsonl'].splitlines()]
    if len(source_rows) != 600 or any(row['source_kind'] != 'synthetic_native_sample' for row in source_rows):
        raise ValueError('Synthetic Native parking source contract changed')
    source = {'path': str(source_path.relative_to(HERE)), 'sha256': sha(source_path),
        'embedded_source': 'files.native_parking_trace.jsonl'}
    if args.kind == 'missing_evidence':
        status, count = 'unverified', 0
    elif args.kind == 'incomplete_motion':
        status, count = 'not_met', 20
    else:
        status, count = 'met', 600
    selected = source_rows[:count]
    if any(row['device_actor_id'] != 1 or row['operator_actor_id'] != 2 or row['device_speed_mps'] > .05
           for row in selected):
        raise ValueError('Stationary device/operator source identity changed')
    method = 'joined original-shaped Native device/operator rows, 600 stationary samples at 20 Hz'
    check = {'status': status, 'method': method, 'sources': [source],
        'source_rows_used': count, 'physical_acceptance_claimed': False,
        'legal_threshold_claimed': False}
    result = {'format': 'c229388-synthetic-parking-physical-outcome-v1',
        'case_id': HERE.name + '__' + args.case, 'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True, 'native_executed': False,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
        'physical_checks': {'maneuver': check}, 'maneuver_completed': status == 'met',
        'realized_observables': {'stationary_parking_source_rows': {'value': count,
            'unit': 'frames', 'method': method, 'sources': [source]}} if status == 'met' else {}}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'status': status, 'result_sha256': sha(path)}))


if __name__ == '__main__':
    main()
