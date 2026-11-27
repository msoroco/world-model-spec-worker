"""CPU proof for saved-source roadway rest and capture lifecycle predicates."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / 'native')]
from finalize import assess_rest

KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def one(case, kind, output):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
    index = manifest['cases'].index(entry)
    fixture = HERE / 'native' / f'fixture-{index}.json'
    hashes = {f'native/fixture-{index}.json': sha(fixture)}
    base = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'original_native_observed': False, 'physical_acceptance_claimed': False}
    if kind == 'lifecycle':
        if EVENTS.index('saved_processing_started') <= EVENTS.index('owner_released'):
            raise ValueError('Saved processing preceded owner release')
        premature = EVENTS[:4] + ['saved_processing_started']
        if 'owner_released' in premature:
            raise ValueError('Premature saved-processing test did not reject')
        base.update(events=EVENTS, exit_code=0,
                    premature_saved_processing_rejected=True)
    else:
        samples = [{'native_frame': i + 1000, 'time_s': (i + 1) / 20,
                    'ego_center_xy_m': [4.2, 0], 'ego_speed_mps': 0}
                   for i in range(600)]
        bodies = [{'native_frame': i + 1000, 'time_s': (i + 1) / 20,
                   'body_vertices_m': [[3.2, -2.5, .5], [5.2, -2.5, .5],
                                       [5.2, 2.5, .5], [3.2, 2.5, .5]]}
                  for i in range(600)]
        if kind == 'incomplete_motion':
            for sample in samples[-100:]:
                sample['ego_speed_mps'] = 4
        if kind == 'missing_evidence':
            bodies = []
        check = assess_rest(samples, bodies, {'edge_x_m': 7}, hashes)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if check['status'] != expected:
            raise ValueError(f'Physical fixture {kind} differs: {check["status"]}')
        base.update(physical_checks={'maneuver': check}, maneuver_completed=expected == 'met',
                    realized_observables={'roadway_rest': check['details']} if expected == 'met' else {})
    write(output, base)
    print(json.dumps({'case_id': entry['case_id'], 'kind': kind,
                      'status': base.get('physical_checks', {}).get('maneuver', {}).get('status')}))


def build():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / case
        rows = []
        for kind in (*KINDS, 'lifecycle'):
            output, log = folder / (kind + '.json'), folder / (kind + '.log')
            command = [sys.executable, '-B', str(Path(__file__).resolve()),
                       '--case', case, '--kind', kind, '--output', str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                status = subprocess.run(command, cwd=HERE.parents[1], stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=30)
            if status.returncode:
                raise ValueError(f'Physical fixture failed: {log}')
            rows.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                         'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c229351-roadway-rest-physical-cpu-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': rows[:3], 'lifecycle': {**life, 'log': rows[3]['log'],
                     'log_sha256': rows[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        write(folder / 'proof.json', proof)
        entry['physical_preparation'] = {'receipt': str((folder / 'proof.json').relative_to(HERE)),
                                         'sha256': sha(folder / 'proof.json')}
    write(HERE / 'execution-manifest.json', manifest)
    print(json.dumps({'physical_fixture_cases': len(manifest['cases'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--kind', choices=(*KINDS, 'lifecycle'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        one(args.case, args.kind, args.output)
    else:
        parser.error('Choose --build or one fixture')
