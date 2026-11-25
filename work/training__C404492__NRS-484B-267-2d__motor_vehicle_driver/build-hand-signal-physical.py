"""Bind synthetic physical outcomes and saved lifecycle for driver hand signal preparation."""
import argparse
import hashlib
import json
from pathlib import Path

from importlib.machinery import SourceFileLoader


HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__preparing_hand_signal'
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']
MODULE = SourceFileLoader('hand_signal_physical',
                          str(HERE / 'prove-hand-signal-physical.py')).load_module()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    args = parser.parse_args()
    poses = MODULE.rows(args.attempt / 'vehicle_poses.jsonl')
    frames = MODULE.rows(args.attempt / 'video_frames.jsonl')
    measured = MODULE.check(poses, frames)
    construction = HERE / 'draft-preparing-hand-signal/primary/construction.json'
    saved = HERE / 'current-hand-signal-saved/primary.json'
    receipt = json.loads(saved.read_text())
    if not (receipt['passed'] and receipt['recorded_only'] and
            receipt['originals_preserved'] and not receipt['missing_evidence']):
        raise ValueError('Exact recorded-only driver hand signal preparation receipt missing')
    premature = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
    if premature.index('saved_processing_started') >= premature.index('owner_released'):
        raise AssertionError('Premature saved processing was not rejected')
    base = HERE / 'physical-proof/preparing_hand_signal'
    sources = [str(args.attempt / 'vehicle_poses.jsonl'),
               str(args.attempt / 'video_frames.jsonl')]
    fixtures = []
    for kind, status in (('complete_motion', 'met'),
                         ('incomplete_motion', 'not_met'),
                         ('missing_evidence', 'unverified')):
        if kind == 'complete_motion':
            observed = measured
        elif kind == 'incomplete_motion':
            changed = [{**row, 'emergency': {**row['emergency'],
                                            'x_m': poses[120]['emergency']['x_m'],
                                            'speed_mps': 0}}
                       if i >= 120 else row for i, row in enumerate(poses)]
            try:
                MODULE.check(changed, frames)
            except ValueError:
                observed = {}
            else:
                raise AssertionError('Incomplete motion accepted')
        else:
            try:
                MODULE.check(poses[:-1], frames)
            except ValueError:
                observed = {}
            else:
                raise AssertionError('Missing evidence accepted')
        result_path = base / (kind + '.json')
        log_path = base / (kind + '.log')
        put(result_path, {
            'case_id': CASE, 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True, 'original_native_observed': False,
            'physical_checks': {'maneuver': {'status': status,
                'method': '600 original-frame-shaped stopped, driver hand signal preparation and travel samples',
                'sources': sources}},
            'maneuver_completed': status == 'met',
            'realized_observables': observed if status == 'met' else {}})
        log_path.write_text(json.dumps({'case_id': CASE, 'kind': kind,
                                        'status': status, 'passed': True}) + '\n')
        fixtures.append({'kind': kind,
                         'command': '.venv-cpu/bin/python work/' + HERE.name +
                                    '/build-hand-signal-physical.py --attempt ' + str(args.attempt),
                         'exit_code': 0,
                         'log': log_path.relative_to(HERE).as_posix(),
                         'log_sha256': sha(log_path),
                         'result': result_path.relative_to(HERE).as_posix(),
                         'result_sha256': sha(result_path)})
    lifecycle_log = base / 'lifecycle.log'
    lifecycle_log.write_text(json.dumps({'events': EVENTS,
                                         'recorded_only_receipt_sha256': sha(saved),
                                         'premature_processing_rejected': True}) + '\n')
    proof = {'format': 'c404492-hand-signal-physical-preparation-v1',
             'case_id': CASE, 'construction_sha256': sha(construction),
             'fixtures': fixtures,
             'lifecycle': {'events': EVENTS, 'exit_code': 0,
                           'recorded_only_receipt_sha256': sha(saved),
                           'log': lifecycle_log.relative_to(HERE).as_posix(),
                           'log_sha256': sha(lifecycle_log)},
             'diagnostic_only': True, 'original_native_observed': False}
    proof_path = base / 'canonical-proof.json'
    put(proof_path, proof)
    print(json.dumps({'case_id': CASE, 'fixtures': len(fixtures),
                      'proof_sha256': sha(proof_path),
                      'original_native_observed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
