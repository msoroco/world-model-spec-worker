"""CPU-test source-bound requested motion and saved-processing order.

The inputs are authored synthetic 600-frame traces, never original Native
motion. This proves only the checker's behavior on complete, incomplete and
missing-source examples.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def motion(case, kind):
    source_case = case if kind == 'complete_motion' else ('witness_2' if case == 'witness_1' else 'witness_1')
    path = HERE / 'v2-source' / source_case / 'native_samples.jsonl'
    if kind == 'missing_evidence':
        return {'status': 'unverified', 'method': '600 joined source frames and requested path',
                'sources': [{'path': str(path.relative_to(HERE)), 'sha256': sha(path)}],
                'reason': 'required Native samples intentionally omitted by fixture'}
    samples = [json.loads(line) for line in path.read_text().splitlines()]
    if len(samples) != 600:
        raise ValueError('Physical fixture needs 600 source rows')
    first, last = samples[0], samples[-1]
    start = first['native_center_xy_m']
    end = last['native_center_xy_m']
    start_heading = math.degrees(math.atan2(*reversed(first['native_forward_xy'])))
    end_heading = math.degrees(math.atan2(*reversed(last['native_forward_xy'])))
    heading_change = abs((end_heading-start_heading+180)%360-180)
    longitudinal_m = end[0]-start[0]
    if case == 'witness_1':
        complete = longitudinal_m > 30 and heading_change < 30
        definition = 'continue through governed region without a U-turn'
    else:
        complete = heading_change > 150 and last['native_lane_id'] != first['native_lane_id']
        definition = 'turn to opposing lane within governed region'
    if (kind == 'complete_motion') != complete:
        raise ValueError('Synthetic source does not realize requested fixture outcome')
    return {'status': 'met' if complete else 'not_met',
            'method': 'source-frame endpoint, heading and lane measurement for '+definition,
            'sources': [{'path': str(path.relative_to(HERE)), 'sha256': sha(path)}],
            'longitudinal_displacement_m': longitudinal_m,
            'heading_change_deg': heading_change,
            'start_lane_id': first['native_lane_id'], 'end_lane_id': last['native_lane_id']}


def lifecycle():
    sequence = ['capture_finished','encoders_closed','restoration_verified',
                'native_exit','owner_released','saved_processing_started']
    def valid(events):
        return events == sequence
    if not valid(sequence) or valid(sequence[:-2] + sequence[-1:]):
        raise AssertionError('Premature saved processing accepted')
    return sequence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=['witness_1','witness_2'], required=True)
    parser.add_argument('--kind', choices=['complete_motion','incomplete_motion','missing_evidence','lifecycle'], required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.kind == 'lifecycle':
        print(json.dumps({'events': lifecycle(), 'premature_rejected': True}))
        return
    check = motion(args.case, args.kind)
    result = {'format': 'c104538-synthetic-physical-outcome-v1',
              'case_id': HERE.name+'__'+args.case,
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'native_executed': False, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False,
              'physical_checks': {'maneuver': check},
              'maneuver_completed': check['status'] == 'met',
              'realized_observables': {'requested_motion': check} if check['status'] == 'met' else {}}
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'case_id': result['case_id'], 'status': check['status'], 'result_sha256': sha(dest)}))


if __name__ == '__main__':
    main()
