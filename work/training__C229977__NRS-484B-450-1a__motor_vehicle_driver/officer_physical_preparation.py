"""Source-shaped officer-candidate motion and lifecycle diagnostics."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def one(state, kind, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'].endswith('__officer_direction_' + state))
    root = HERE / 'diagnostic-source' / ('officer_direction_' + state)
    vehicle = HERE / 'diagnostic-source' / 'probe_2' / 'vehicle-trace.jsonl'
    officer = root / 'officer-trace.jsonl'
    rows = [json.loads(line) for line in vehicle.read_text().splitlines()]
    actors = [json.loads(line) for line in officer.read_text().splitlines()]
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'physical_acceptance_claimed': False}
    if kind == 'lifecycle':
        base.update(events=EVENTS, exit_code=0, premature_saved_processing_rejected=True)
    else:
        if kind == 'incomplete_motion':
            for row in rows:
                row['speed_mps'] = 4.0
        if kind == 'missing_evidence':
            actors.pop()
        full = (len(rows) == len(actors) == 600 and
                all(row.get('frame') == i and actors[i].get('frame') == i and
                    row.get('native_frame') == actors[i].get('native_frame') and
                    abs(float(row['time_s']) - float(actors[i]['time_s'])) < 1e-4
                    for i, row in enumerate(rows)))
        actor_correct = all((row.get('actor_id') is not None) == (state == 'present') for row in actors)
        stopped = any(row.get('speed_mps', 1) <= .05 for row in rows)
        observed = ('unverified' if not full or not actor_correct else
                    'met' if stopped else 'not_met')
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if observed != expected:
            raise ValueError(f'Officer physical diagnostic mismatch: {kind}/{observed}')
        base.update(physical_checks={'maneuver': {
            'status': observed,
            'method': '600 joined source-shaped vehicle and officer-candidate rows; diagnostic stop tolerance only',
            'sources': [str(vehicle.relative_to(HERE)), str(officer.relative_to(HERE))]}},
            maneuver_completed=observed == 'met',
            realized_observables={
                'rest_frames': sum(row['speed_mps'] <= .05 for row in rows),
                'officer_candidate_present': state == 'present',
                'identity_direction_compliance_verified': False} if observed == 'met' else {},
            source_sha256=sha(vehicle), officer_source_sha256=sha(officer))
    write(output, base)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for state in ('absent', 'present'):
        entry = next(row for row in manifest['cases'] if row['case_id'].endswith('__officer_direction_' + state))
        folder = HERE / 'physical-proof' / ('officer_direction_' + state)
        refs = []
        for kind in (*KINDS, 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            folder.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, '-B', str(Path(__file__).resolve()),
                       '--state', state, '--kind', kind, '--output', str(output)]
            with log.open('w') as stream:
                process = subprocess.run(command, cwd=HERE.parents[1], stdout=stream,
                                         stderr=subprocess.STDOUT, timeout=30,
                                         env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            log.write_text(log.read_text().rstrip() + '\n')
            if process.returncode:
                raise ValueError(f'Officer physical diagnostic failed: {log}')
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                         'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c229977-officer-physical-cpu-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'], 'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        write(folder / 'proof.json', proof)
        entry['physical_preparation'] = {'receipt': str((folder / 'proof.json').relative_to(HERE)),
                                         'sha256': sha(folder / 'proof.json')}
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(sha(path))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--state', choices=('absent', 'present'))
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.state and args.kind and args.output:
        one(args.state, args.kind, args.output)
    else:
        parser.error('Choose --build or a fixture')
