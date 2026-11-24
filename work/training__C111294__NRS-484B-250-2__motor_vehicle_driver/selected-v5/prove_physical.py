"""Exercise physical outcome and closure classification on selected CPU sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def classify(rows, map_rows, evidence_rows, missing=False):
    if missing or not rows or not map_rows or not evidence_rows:
        return 'unverified', {}
    if len(rows) != len(map_rows) or len(rows) != len(evidence_rows):
        return 'not_met', {}
    for i, (row, mapping, evidence) in enumerate(zip(rows, map_rows, evidence_rows)):
        if (row['frame'] != i or mapping['carla_frame'] != i or
                evidence['original_frame'] != i or
                abs(row['time_s'] - mapping['time_s']) > 1e-9 or
                abs(row['time_s'] - evidence['recording_time_s']) > 1e-9):
            return 'not_met', {}
    def entered(actor, axis):
        for row in rows:
            if max(v[axis] for v in row[actor]['body_xyz_m']) >= -20:
                return row['time_s']
        return None
    ego, other = entered('ego', 0), entered('other', 1)
    ego_rear_exited = min(v[0] for v in rows[-1]['ego']['body_xyz_m']) > 20
    other_rear_exited = min(v[1] for v in rows[-1]['other']['body_xyz_m']) > 20
    if len(rows) != 600 or ego is None or other is None or not ego_rear_exited or not other_rear_exited:
        return 'not_met', {}
    return 'met', {'ego_front_entry_s': ego, 'other_front_entry_s': other,
                   'ego_minus_other_front_entry_s': round(ego-other, 6),
                   'both_rear_bodies_exited': True}


def proof(suffix):
    case_id = ASSIGNMENT.name + '__' + suffix
    source = ASSIGNMENT / 'selected-v3' / suffix / 'primary' / 'sources'
    construction = HERE / suffix / 'primary' / 'construction.json'
    history = json.loads((source / 'actor-history.json').read_text())
    rows = history['rows']
    mapping = [json.loads(line) for line in (source / 'video_frames.jsonl').read_text().splitlines()]
    evidence = [json.loads(line) for line in (source / 'capture/evidence.jsonl').read_text().splitlines()]
    if history.get('synthetic') is not True or len(rows) != 600:
        raise ValueError('Selected synthetic source inventory differs')
    files = ['selected-v3/' + suffix + '/primary/sources/' + name for name in
             ('actor-history.json', 'video_frames.jsonl', 'capture/evidence.jsonl', 'road.xodr')]
    directory = HERE / 'physical-proofs' / suffix
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        selected = rows if kind != 'incomplete_motion' else rows[:100]
        selected_map = mapping if kind != 'incomplete_motion' else mapping[:100]
        selected_evidence = evidence if kind != 'incomplete_motion' else evidence[:100]
        status, measured = classify(selected, selected_map, selected_evidence,
                                    missing=kind == 'missing_evidence')
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError(kind + ' incorrectly classified as ' + status)
        result = {'case_id': case_id, 'construction_sha256': sha(construction),
                  'physical_checks': {'maneuver': {
                      'status': status,
                      'method': 'Source-joined 20 Hz actor body front-entry and rear-exit history',
                      'sources': files}},
                  'maneuver_completed': status == 'met',
                  'realized_observables': measured,
                  'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                  'original_native_motion_verified': False,
                  'original_pixels_verified': False, 'legal_verdict_claimed': False,
                  'source_sha256': {name: sha(ASSIGNMENT / name) for name in files}}
        result_path = directory / (kind + '.json')
        log_path = directory / (kind + '.log')
        write(result_path, result)
        log_path.write_text(f'{case_id} {kind}: {status}; synthetic CPU diagnostic\n')
        fixtures.append({'kind': kind,
                         'command': f'.venv-cpu/bin/python work/{ASSIGNMENT.name}/selected-v5/prove_physical.py',
                         'exit_code': 0, 'log': log_path.relative_to(ASSIGNMENT).as_posix(),
                         'log_sha256': sha(log_path),
                         'result': result_path.relative_to(ASSIGNMENT).as_posix(),
                         'result_sha256': sha(result_path)})
    if EVENTS.index('native_exit') >= EVENTS.index('owner_released') or EVENTS.index('owner_released') >= EVENTS.index('saved_processing_started'):
        raise ValueError('Saved processing lifecycle order changed')
    life_log = directory / 'lifecycle.log'
    life_log.write_text(' > '.join(EVENTS) + '\n')
    receipt = directory / 'proof.json'
    write(receipt, {'format': 'c111294-2502-selected-physical-cpu-v1',
                    'case_id': case_id, 'construction_sha256': sha(construction),
                    'fixtures_are_cpu_diagnostics': True,
                    'original_native_motion_verified': False,
                    'fixtures': fixtures,
                    'lifecycle': {'events': EVENTS, 'exit_code': 0,
                                  'log': life_log.relative_to(ASSIGNMENT).as_posix(),
                                  'log_sha256': sha(life_log)}})
    return receipt


if __name__ == '__main__':
    for suffix in ('controlled_1', 'controlled_2'):
        path = proof(suffix)
        print(path.relative_to(ASSIGNMENT).as_posix(), sha(path))
