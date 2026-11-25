"""Source-bound controlled comparison for NRS 484B.603(1) intersection probes."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def compare(a, b):
    if len(a) != len(b) or len(a) != 600:
        raise ValueError('Original Native sample length differs')
    if a[0].get('ego_position_m') != b[0].get('ego_position_m') or a[0].get('ego_velocity_mps') != b[0].get('ego_velocity_mps'):
        raise ValueError('Initial ego state changed')
    for i, (left, right) in enumerate(zip(a, b)):
        if left.get('frame') != right.get('frame') or left.get('frame') != i or left.get('time_s') != right.get('time_s'):
            raise ValueError('Frame/time pairing changed')
        if (left.get('ego_role'), left.get('other_role')) != ('motor_vehicle_driver', 'motor_vehicle_driver') or (right.get('ego_role'), right.get('other_role')) != ('motor_vehicle_driver', 'motor_vehicle_driver'):
            raise ValueError('Participant roles changed')
        if left.get('other_position_m') != right.get('other_position_m'):
            raise ValueError('Other-traffic trajectory changed')
        if left.get('ego_position_m', [None])[0] != right.get('ego_position_m', [None])[0]:
            raise ValueError('Ego lateral starting or path coordinate changed')
    return {'frames_per_case': 600, 'fixed_other_traffic': True, 'fixed_initial_ego': True}


def audit(args):
    left = Path(args.attempt_a).resolve(); right = Path(args.attempt_b).resolve()
    for path in (left, right):
        provenance = json.loads((path / 'acquisition-provenance.json').read_text())
        if provenance.get('provenance_kind') != 'native' or provenance.get('native_executed') is not True or provenance.get('diagnostic_fixture') is True:
            raise ValueError('Original Native acquisition required')
        result = json.loads((path / 'result.json').read_text())
        if result.get('accepted') is not False or result.get('legal_verdict_claimed') is not False:
            raise ValueError('Case has unsupported legal acceptance')
    if sha(left / 'road.xodr') != sha(right / 'road.xodr'):
        raise ValueError('Controlled comparison map changed')
    lc = json.loads((left / 'candidate-selection.json').read_text())
    rc = json.loads((right / 'candidate-selection.json').read_text())
    if lc.get('candidate_id') != rc.get('candidate_id'):
        raise ValueError('Controlled pair mixed candidate conditions')
    result = compare(rows(left / 'native_samples.jsonl'), rows(right / 'native_samples.jsonl'))
    result.update({'format': 'c111294-603-1-source-comparison-v1', 'passed': True,
                   'candidate_id': lc.get('candidate_id'), 'map_sha256': sha(left / 'road.xodr'),
                   'native_samples_sha256': {'probe_a': sha(left / 'native_samples.jsonl'),
                                             'probe_b': sha(right / 'native_samples.jsonl')},
                   'legal_outcome_claimed': False,
                   'physical_hazard_necessity_claimed': False})
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    return result


def selftest(negative):
    base = {'frame': 0, 'time_s': 0.0, 'ego_position_m': [0.0, -75.0, 0.0],
            'ego_velocity_mps': [0.0, 12.9, 0.0], 'other_position_m': [-30.0, 0.0, 0.0],
            'ego_role': 'motor_vehicle_driver', 'other_role': 'motor_vehicle_driver'}
    a = [dict(base, frame=i, time_s=i / 20, other_position_m=[-30 + i * 0.25, 0, 0]) for i in range(600)]
    b = json.loads(json.dumps(a))
    if negative:
        b[200]['other_position_m'][0] += 1
        compare(a, b)
        raise AssertionError('Changed traffic accepted')
    result = compare(a, b)
    for key, value in (('ego_position_m', [1, -75, 0]), ('other_role', 'pedestrian')):
        changed = json.loads(json.dumps(b)); changed[0][key] = value
        try:
            compare(a, changed)
        except ValueError:
            continue
        raise AssertionError('Changed controlled condition accepted')
    return dict(result, original_capture_attested=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--attempt-a')
    parser.add_argument('--attempt-b')
    parser.add_argument('--output')
    arguments = parser.parse_args()
    print(json.dumps(selftest(arguments.negative) if arguments.self_test else audit(arguments), indent=2))
