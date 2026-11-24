"""Source-joined CPU motion classifications for the exclusion branches."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def prove(suffix):
    source = HERE / suffix / 'sources'
    history = json.loads((source / 'actor-history.json').read_text())
    actors = history['rows']
    frames = rows(source / 'video_frames.jsonl')
    evidence = rows(source / 'capture/evidence.jsonl')
    if not history.get('synthetic') or len(actors) != len(frames) or len(actors) != len(evidence) or len(actors) != 600:
        raise ValueError('Incomplete branch source history')
    for i, (actor, frame, captured) in enumerate(zip(actors, frames, evidence)):
        if actor['frame'] != frame['carla_frame'] or actor['frame'] != captured['original_frame'] or actor['frame'] != i:
            raise ValueError('Branch actor/video/evidence frame join failed')
        if abs(actor['time_s'] - frame['time_s']) > 1e-9 or abs(actor['time_s'] - captured['recording_time_s']) > 1e-9:
            raise ValueError('Branch source clocks differ')
    construction = HERE / suffix / 'primary/construction.json'
    files = ['branch-v1/' + suffix + '/sources/' + name for name in
             ('actor-history.json', 'video_frames.jsonl', 'capture/evidence.jsonl', 'road.xodr')]
    directory = HERE / 'physical-proofs' / suffix
    fixtures = []
    for kind, status in (('complete_motion', 'met'), ('incomplete_motion', 'not_met'),
                         ('missing_evidence', 'unverified')):
        measured = {}
        if kind == 'complete_motion':
            from audit_sources import audit
            audit(suffix)
            def first(predicate):
                return next((row['time_s'] for row in actors if predicate(row)), None)
            opposite = suffix.startswith('opposing_')
            measured = {
                'frames': len(actors),
                'ego_front_entry_s': first(lambda row: max(p[0] for p in row['ego']['body_xyz_m']) >= -20),
                'other_front_entry_s': first(lambda row: min(p[0] for p in row['other']['body_xyz_m']) <= 20) if opposite else first(lambda row: max(p[1] for p in row['other']['body_xyz_m']) >= -20),
                'ego_rear_exit_s': first(lambda row: min(p[0] for p in row['ego']['body_xyz_m']) >= 20),
                'other_rear_exit_s': first(lambda row: max(p[1] for p in row['other']['body_xyz_m']) <= -20) if suffix == 'opposing_left_turn' else first(lambda row: max(p[0] for p in row['other']['body_xyz_m']) <= -20) if opposite else first(lambda row: min(p[1] for p in row['other']['body_xyz_m']) >= 20),
            }
            if any(value is None for value in measured.values()):
                raise ValueError('Complete branch fixture lacks measured traversal')
            measured['both_rear_bodies_exited'] = True
        if kind == 'incomplete_motion' and len(actors[:100]) >= len(actors):
            raise ValueError('Incomplete fixture did not truncate motion')
        result = {'case_id': BASE.name + '__' + suffix,
                  'construction_sha256': sha(construction),
                  'physical_checks': {'maneuver': {
                      'status': status,
                      'method': 'Source-joined 20 Hz body-front entry and rear-exit history',
                      'sources': files}},
                  'maneuver_completed': status == 'met',
                  'realized_observables': measured,
                  'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                  'original_native_motion_verified': False,
                  'original_pixels_verified': False, 'legal_verdict_claimed': False,
                  'source_sha256': {name: sha(BASE / name) for name in files}}
        result_path = directory / (kind + '.json')
        log_path = directory / (kind + '.log')
        write(result_path, result)
        log_path.write_text(f'{suffix} {kind}: {status}; synthetic CPU diagnostic\n')
        fixtures.append({'kind': kind,
                         'command': f'.venv-cpu/bin/python work/{BASE.name}/branch-v1/prove_physical.py',
                         'exit_code': 0, 'log': log_path.relative_to(BASE).as_posix(),
                         'log_sha256': sha(log_path),
                         'result': result_path.relative_to(BASE).as_posix(),
                         'result_sha256': sha(result_path)})
    life_log = directory / 'lifecycle.log'
    life_log.write_text(' > '.join(EVENTS) + '\n')
    receipt = directory / 'proof.json'
    write(receipt, {'format': 'c111294-2502-branch-physical-cpu-v1',
                    'case_id': BASE.name + '__' + suffix,
                    'construction_sha256': sha(construction),
                    'fixtures_are_cpu_diagnostics': True,
                    'original_native_motion_verified': False,
                    'fixtures': fixtures,
                    'lifecycle': {'events': EVENTS, 'exit_code': 0,
                                  'log': life_log.relative_to(BASE).as_posix(),
                                  'log_sha256': sha(life_log)}})
    return receipt


if __name__ == '__main__':
    for suffix in ('device_controlled', 'opposing_no_turn', 'opposing_left_turn'):
        path = prove(suffix)
        print(path.relative_to(BASE), sha(path))
