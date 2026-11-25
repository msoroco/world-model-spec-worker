"""Synthetic source test of three physical outcomes and ownership ordering."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = HERE / 'current-c1/exception_3_1/fixture-native-raw-actors.jsonl'
CONSTRUCTION = HERE / 'current-c1/exception_3_1/primary/construction.json'
OUT = HERE / 'physical-fixtures'
CASE = 'training__C146314__NRS-484B-210-1__motor_vehicle_driver__exception_3_1'
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def classify(rows):
    if not rows or any('ego' not in row or 'lead' not in row for row in rows):
        return 'unverified', {}
    before = any(row['ego']['center_native_xyz_m'][0] + 2 <
                 row['lead']['center_native_xyz_m'][0] - 2 for row in rows)
    after_right = any(row['ego']['center_native_xyz_m'][0] - 2 >
                      row['lead']['center_native_xyz_m'][0] + 2 and
                      row['ego']['center_native_xyz_m'][1] <
                      row['lead']['center_native_xyz_m'][1] - 1 for row in rows)
    right_during = any(row['ego']['center_native_xyz_m'][1] <
                       row['lead']['center_native_xyz_m'][1] - 1 for row in rows)
    evidence = {'initially_behind': before, 'right_during': right_during,
                'ahead_while_right': after_right, 'frames': len(rows)}
    return ('met' if all((before, right_during, after_right)) else 'not_met'), evidence


def lifecycle(events):
    if events != EVENTS:
        raise ValueError('Saved processing precedes Native ownership closure')
    return True


def main():
    OUT.mkdir(exist_ok=True)
    rows = [json.loads(line) for line in SOURCE.read_text().splitlines()]
    assert len(rows) == 600 and all(row.get('source_kind') == 'synthetic_fixture'
                                    for row in rows)
    scenarios = {'complete_motion': rows,
                 'incomplete_motion': rows[:20],
                 'missing_evidence': [{'frame': 0, 'ego': rows[0]['ego']}]}
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}
    receipts = []
    for name, data in scenarios.items():
        status, evidence = classify(data)
        assert status == expected[name], (name, status)
        result_path = OUT / (name + '-result.json')
        log_path = OUT / (name + '-test.log')
        result = {'case_id': CASE, 'provenance_kind': 'synthetic_fixture',
                  'diagnostic_fixture': True,
                  'physical_checks': {'maneuver': {
                      'status': status,
                      'method': 'Frame-joined ego/lead body center sequence; engineering diagnostic only',
                      'sources': [{'path': str(SOURCE.relative_to(ROOT)),
                                   'sha256': sha(SOURCE)}],
                      'observations': evidence}},
                  'maneuver_completed': status == 'met',
                  'realized_observables': evidence if status == 'met' else {},
                  'legal_verdict': None}
        write_json(result_path, result)
        log_path.write_text('PASS ' + name + ': ' + status + '; synthetic fixture only\n')
        receipts.append({'kind': name,
                         'command': '.venv-cpu/bin/python work/' + ROOT.name + '/native/prove_physical_lifecycle.py',
                         'exit_code': 0, 'log': str(log_path.relative_to(ROOT)),
                         'log_sha256': sha(log_path),
                         'result': str(result_path.relative_to(ROOT)),
                         'result_sha256': sha(result_path)})
    assert lifecycle(EVENTS)
    try:
        lifecycle(EVENTS[:4] + EVENTS[5:] + EVENTS[4:5])
        raise AssertionError('Out-of-order saved processing was accepted')
    except ValueError as error:
        assert str(error) == 'Saved processing precedes Native ownership closure'
    life_log = OUT / 'lifecycle-test.log'
    life_log.write_text('PASS ordered capture closure and owner release; rejected saved processing before owner release\n')
    proof = {'format': 'c146314-physical-lifecycle-cpu-v1', 'case_id': CASE,
             'construction_sha256': sha(CONSTRUCTION), 'fixtures': receipts,
             'lifecycle': {'events': EVENTS, 'exit_code': 0,
                           'log': str(life_log.relative_to(ROOT)),
                           'log_sha256': sha(life_log)},
             'physical_or_legal_acceptance': False}
    write_json(OUT / 'proof.json', proof)
    print('PASS three synthetic physical outcomes and ordered lifecycle; no Native claim')


if __name__ == '__main__':
    main()
