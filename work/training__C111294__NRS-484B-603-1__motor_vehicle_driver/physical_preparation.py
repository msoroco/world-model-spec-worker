"""Test source-shaped 600-frame speed-profile completion and Native lifecycle."""
import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def classify(rows, suffix):
    if len(rows) != 600 or [r.get('native_frame') for r in rows] != list(range(100, 700)):
        return 'unverified'
    if any(r.get('ego_actor_id') != 101 or r.get('other_actor_id') != 202 or
           r.get('ego_role') != 'motor_vehicle_driver' for r in rows):
        return 'unverified'
    if any(abs(r['time_s'] - (i + 1) / 20) > 1e-6 for i, r in enumerate(rows)):
        return 'unverified'
    y = [r['ego_position_m'][1] for r in rows]
    if not any(v < -7 for v in y) or not any(v > 7 for v in y):
        return 'not_met'
    if any(b <= a for a, b in zip(y, y[1:])):
        return 'not_met'
    def average(lo, hi):
        speeds = [math.sqrt(sum(v*v for v in r['ego_velocity_mps'])) / .44704
                  for r in rows if lo <= r['ego_position_m'][1] < hi]
        return sum(speeds) / len(speeds) if speeds else None
    early, before, crossing = average(-60, -50), average(-20, -7), average(-7, 7)
    if None in (early, before, crossing):
        return 'unverified'
    measured_decrease = early - before
    if suffix == 'probe_a':
        return 'met' if measured_decrease >= 3 and crossing <= before + 2 else 'not_met'
    return 'met' if measured_decrease <= 1 and crossing >= before - 1 else 'not_met'


def fixture(suffix, kind, output):
    construction = HERE / f'current-v2-{suffix}-diagnostic/construction.json'
    source = HERE / f'current-v2-{suffix}-source/native_samples.jsonl'
    case = HERE.name + '__' + suffix
    result = {'case_id': case, 'construction_sha256': sha(construction),
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'original_native_observed': False, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    if kind == 'lifecycle':
        result.update(events=EVENTS, exit_code=0,
                      negative_premature_saved_processing_rejected=True)
    else:
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in rows[100:]:
                row['ego_position_m'][1] = -10.0
        elif kind == 'missing_evidence':
            rows.pop()
        status = classify(rows, suffix)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Physical fixture outcome differs: ' + kind + '/' + status)
        result.update(physical_checks={'maneuver': {
            'status': status,
            'method': '600 joined original-frame ego positions, velocities and other-vehicle identity; measured intersection crossing and engineering speed-profile contrast',
            'sources': [source.relative_to(ROOT).as_posix(),
                        (HERE / f'current-v2-{suffix}-source/road.xodr').relative_to(ROOT).as_posix()]}},
            maneuver_completed=status == 'met',
            realized_observables={'joined_frames': 600, 'crossed_intersection': True}
            if status == 'met' else {}, source_sha256=sha(source))
    write(output, result)
    print(json.dumps({'case_id': case, 'kind': kind,
                      'status': result.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    index = []
    for suffix in ('probe_a', 'probe_b'):
        case = HERE.name + '__' + suffix
        folder = HERE / 'physical-proof' / suffix
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output, log = folder / (kind + '.json'), folder / (kind + '.log')
            folder.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(Path(__file__).resolve()),
                       '--case', suffix, '--kind', kind, '--output', str(output)]
            with log.open('w') as stream:
                run = subprocess.run(command, cwd=ROOT, stdout=stream,
                                     stderr=subprocess.STDOUT, timeout=30)
            if run.returncode:
                raise ValueError('Physical fixture failed: ' + str(log))
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log),
                         'result': output.relative_to(HERE).as_posix(),
                         'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c111294-synthetic-physical-preparation-v1',
                 'case_id': case,
                 'construction_sha256': sha(HERE / f'current-v2-{suffix}-diagnostic/construction.json'),
                 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        path = folder / 'proof.json'
        write(path, proof)
        index.append({'case_id': case, 'receipt': path.relative_to(HERE).as_posix(),
                      'sha256': sha(path)})
    write(HERE / 'physical-proof/index.json', {'cases': index, 'diagnostic_only': True})
    print(json.dumps({'physical_fixture_cases': len(index)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case', choices=('probe_a', 'probe_b'))
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error('Select --build or one fixture')
