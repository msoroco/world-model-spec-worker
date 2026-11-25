"""Test source-bound bus completion classifications on synthetic data only."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('probe_1', 'probe_2', 'probe_3'), required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion',
                                           'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.kind == 'lifecycle':
        print(json.dumps({'events': ['capture_finished', 'encoders_closed',
            'restoration_verified', 'native_exit', 'owner_released',
            'saved_processing_started'], 'premature_processing_rejected': True}))
        return
    if not args.output:
        parser.error('--output required')
    path = HERE / 'cases' / args.case / 'diagnostic.json'
    data = json.loads(path.read_text())['files']
    rows = [json.loads(line) for line in data['bus-traffic-poses.jsonl'].splitlines()]
    if len(rows) != 600 or any(r['video_frame'] != i or r['bus_id'] != 1 or
                               r['other_vehicle_id'] != 2 for i, r in enumerate(rows)):
        raise ValueError('Synthetic bus Native source identity changed')
    source = {'path': str(path.relative_to(HERE)), 'sha256': sha(path),
              'embedded_source': 'files.bus-traffic-poses.jsonl'}
    status, count = {'complete_motion': ('met', 600),
                     'incomplete_motion': ('not_met', 20),
                     'missing_evidence': ('unverified', 0)}[args.kind]
    method = 'joined 600 original-shaped bus/traffic frames and source-reviewed curb/loading geometry'
    check = {'status': status, 'method': method, 'sources': [source],
             'source_rows_used': count, 'physical_acceptance_claimed': False,
             'legal_threshold_claimed': False}
    result = {'format': 'c149507-synthetic-bus-physical-outcome-v1',
        'case_id': HERE.name + '__' + args.case,
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'native_executed': False, 'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False, 'physical_checks': {'maneuver': check},
        'maneuver_completed': status == 'met',
        'realized_observables': {'bus_source_rows': {'value': count,
            'unit': 'frames', 'method': method, 'sources': [source]}}
            if status == 'met' else {}}
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'status': status,
                      'result_sha256': sha(target)}))


if __name__ == '__main__':
    main()
