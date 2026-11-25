"""CPU-test requested rider motion on synthetic source rows only."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KINDS = {'controlled_1': 'mounted-obey', 'controlled_2': 'mounted-turn',
         'controlled_3': 'dismounted-turn'}
for _machine in ('electric_bicycle', 'electric_scooter'):
    KINDS.update({f'{_machine}_obey': 'mounted-obey',
                  f'{_machine}_turn': 'mounted-turn',
                  f'{_machine}_dismount': 'dismounted-turn'})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(suffix):
    if suffix.startswith(('electric_bicycle_', 'electric_scooter_')):
        return HERE / 'electric-drafts' / suffix / 'rider_native_samples.jsonl'
    return HERE / ('v2-' + KINDS[suffix] + '-primary-source') / 'rider_native_samples.jsonl'


def read(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) != 600 or [r['frame'] for r in rows] != list(range(600)):
        raise ValueError('Physical fixture needs 600 joined source rows')
    return rows


def motion(suffix, kind):
    if suffix.startswith(('electric_bicycle_', 'electric_scooter_')):
        machine, behavior = suffix.rsplit('_', 1)
        alternate = machine + '_' + {'obey': 'turn', 'turn': 'obey',
                                     'dismount': 'turn'}[behavior]
    else:
        alternate = {'controlled_1': 'controlled_2', 'controlled_2': 'controlled_1',
                     'controlled_3': 'controlled_2'}[suffix]
    path = source(suffix if kind != 'incomplete_motion' else alternate)
    evidence = [{'path': str(path.relative_to(HERE)), 'sha256': sha(path)}]
    if kind == 'missing_evidence':
        return {'status': 'unverified', 'method': 'source-row posture/turn ordering',
                'sources': evidence, 'reason': 'rider source intentionally omitted in fixture'}
    rows = read(path)
    turns = [r for r in rows if r['u_turn_active']]
    dismount = next((i for i, r in enumerate(rows) if not r['mounted']), None)
    if suffix == 'controlled_1' or suffix.endswith('_obey'):
        complete = not turns and dismount is None
        definition = 'remain mounted and avoid the prohibited U-turn'
    elif suffix == 'controlled_2' or suffix.endswith('_turn'):
        complete = bool(turns) and dismount is None and all(r['mounted'] for r in turns)
        definition = 'remain mounted during the requested U-turn'
    else:
        complete = (dismount is not None and bool(turns) and dismount < turns[0]['frame']
                    and all(r['walking_machine'] and not r['mounted'] for r in turns)
                    and all(not r['mounted'] for r in rows[dismount:]))
        machine_name = suffix.rsplit('_', 1)[0].replace('_', ' ') if suffix != 'controlled_3' else 'bicycle'
        definition = 'dismount before turning and walk the ' + machine_name + ' throughout the turn'
    if complete != (kind == 'complete_motion'):
        raise ValueError('Synthetic fixture does not realize requested outcome')
    return {'status': 'met' if complete else 'not_met',
            'method': '600 source-row posture, machine-state, and turn-frame measurement for ' + definition,
            'sources': evidence, 'turn_frames': len(turns), 'dismount_frame': dismount,
            'pedestrian_rule_compliance_verified': False}


def lifecycle():
    events = ['capture_finished', 'encoders_closed', 'restoration_verified',
              'native_exit', 'owner_released', 'saved_processing_started']
    if events.index('saved_processing_started') <= events.index('owner_released'):
        raise AssertionError('Premature saved processing accepted')
    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=KINDS, required=True)
    parser.add_argument('--kind', choices=['complete_motion', 'incomplete_motion',
                                          'missing_evidence', 'lifecycle'], required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.kind == 'lifecycle':
        print(json.dumps({'events': lifecycle(), 'premature_rejected': True}))
        return
    if not args.output:
        parser.error('--output required for motion fixtures')
    check = motion(args.case, args.kind)
    result = {'format': 'c104538-rider-synthetic-physical-outcome-v1',
              'case_id': HERE.name + '__' + args.case,
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'native_executed': False, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False,
              'physical_checks': {'maneuver': check},
              'maneuver_completed': check['status'] == 'met',
              'realized_observables': {'requested_motion': check} if check['status'] == 'met' else {}}
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'status': check['status'],
                      'result_sha256': sha(dest)}))


if __name__ == '__main__':
    main()
