"""Source-bound diagnostic completion and ownership ordering probes."""

import argparse
import hashlib
import json
from pathlib import Path

from measure_sidewalk import measure_core_join


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def result(attempt, case_id, kind):
    attempt = Path(attempt)
    rows_path = attempt / 'native-rows.jsonl'
    if kind == 'missing_evidence':
        observed = {}
        status = 'unverified'
        sources = {'native-rows.jsonl': None}
        method = 'Missing diagnostic Native history prevents completion assessment'
    else:
        observed = measure_core_join(attempt, case_id)
        rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
        if kind == 'incomplete_motion':
            start = rows[0]['vehicle_xy_m']
            changed = [{**row, 'vehicle_xy_m': start,
                        'vehicle_speed_mps': 0.0} for row in rows]
            encoded = (json.dumps(changed, separators=(',', ':')) + '\n').encode()
            status = 'not_met'
            sources = {'diagnostic-counterfactual-rows': sha_bytes(encoded)}
            method = '600 source-joined frames with no body progression toward sidewalk'
            observed = {}
        else:
            if (observed['first_observed_body_sidewalk_cross_frame'] is None or
                    observed['frame_count'] != 600):
                raise ValueError('Complete diagnostic body crossing absent')
            status = 'met'
            sources = {'native-rows.jsonl': sha_bytes(rows_path.read_bytes()),
                       'captured-source-hashes.json':
                           sha_bytes((attempt / 'captured-source-hashes.json').read_bytes())}
            method = '600 source-joined frames and complete body crossing of sidewalk'
    return {'case_id': case_id,
            'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True,
            'maneuver_completed': status == 'met',
            'physical_checks': {'maneuver': {'status': status,
                                             'method': method,
                                             'sources': sources}},
            'realized_observables': observed,
            'original_native_observed': False,
            'physical_acceptance': False,
            'legal_verdict': None}


def lifecycle():
    events = ['capture_finished', 'encoders_closed',
              'restoration_verified', 'native_exit',
              'owner_released', 'saved_processing_started']
    prerequisites = {'encoders_closed': 'capture_finished',
                     'restoration_verified': 'encoders_closed',
                     'native_exit': 'restoration_verified',
                     'owner_released': 'native_exit',
                     'saved_processing_started': 'owner_released'}
    seen = set()
    for event in events:
        if event in prerequisites and prerequisites[event] not in seen:
            raise ValueError('Saved processing precedes Native ownership closure')
        seen.add(event)
    return {'events': events, 'exit_code': 0,
            'scope': 'CPU lifecycle ordering protocol only'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True,
                        choices=('complete_motion', 'incomplete_motion',
                                 'missing_evidence', 'lifecycle'))
    args = parser.parse_args()
    if args.case not in {Path(__file__).resolve().parent.parent.name + '__' + suffix
                         for suffix in ('stop_before_sidewalk', 'cross_without_stop')}:
        raise ValueError('Another exact case selected')
    value = lifecycle() if args.kind == 'lifecycle' else result(
        args.attempt, args.case, args.kind)
    print(json.dumps(value, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
