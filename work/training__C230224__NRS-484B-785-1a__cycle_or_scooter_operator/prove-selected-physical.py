"""Exercise scooter motion assessment with source-bound synthetic diagnostic rows."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUFFIXES = ('controlled_1', 'controlled_at_cap', 'controlled_2')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assess(suffix, kind):
    path = HERE / 'cases' / suffix / 'diagnostic.json'
    source = json.loads(path.read_text())['files']['native_rider_trace.jsonl']
    rows = [json.loads(line) for line in source.splitlines()]
    if len(rows) != 600 or any(r['source_kind'] != 'synthetic_native_sample' for r in rows):
        raise ValueError('Synthetic source row contract changed')
    source_ref = {'path': str(path.relative_to(HERE)), 'sha256': sha(path),
                  'embedded_source': 'files.native_rider_trace.jsonl'}
    if kind == 'missing_evidence':
        check = {'status': 'unverified', 'method': 'source-row scooter displacement and identity join',
                 'sources': [source_ref], 'reason': 'source rows deliberately withheld from assessor'}
    else:
        selected = rows if kind == 'complete_motion' else rows[:20]
        if any(r['device_actor_id'] != 1 or r['rider_actor_id'] != 2 for r in selected):
            raise ValueError('Scooter and rider source identity changed')
        start, end = selected[0]['device_center_xy_m'], selected[-1]['device_center_xy_m']
        progress = end[0] - start[0]
        complete = progress >= 10 and len(selected) == 600
        if complete != (kind == 'complete_motion'):
            raise ValueError('Diagnostic did not realize requested motion outcome')
        check = {'status': 'met' if complete else 'not_met',
                 'method': 'joined scooter Native source rows: 600 samples and >=10 m forward travel',
                 'sources': [source_ref], 'source_rows_used': len(selected),
                 'forward_progress_m': progress,
                 'physical_acceptance_claimed': False}
    return check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=SUFFIXES, required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'), required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.kind == 'lifecycle':
        events = ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']
        assert events.index('owner_released') < events.index('saved_processing_started')
        print(json.dumps({'events': events, 'premature_processing_rejected': True}))
        return
    if not args.output:
        parser.error('--output required')
    check = assess(args.case, args.kind)
    result = {'format': 'c230224-scooter-synthetic-physical-outcome-v1',
              'case_id': HERE.name + '__' + args.case,
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'native_executed': False, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False,
              'physical_checks': {'maneuver': check},
              'maneuver_completed': check['status'] == 'met',
              'realized_observables': {'scooter_forward_progress_m': {'value': check['forward_progress_m'],
                  'unit': 'm', 'method': check['method'], 'sources': check['sources']}}
                  if check['status'] == 'met' else {}}
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'status': check['status'], 'result_sha256': sha(dest)}))


if __name__ == '__main__':
    main()
