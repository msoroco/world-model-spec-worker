"""CPU fixture proof of pedestrian motion and capture lifecycle guards.

These deterministic examples are synthetic and never claim Native execution.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from physical_geometry_audit import evaluate_crossing_completion

ROOT = Path(__file__).resolve().parent
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def body_rows(scene, endpoint_fraction):
    start = scene['route_xy_m'][0]
    end = scene['route_xy_m'][-1]
    rows = []
    for index in range(400):
        fraction = index / 399 * endpoint_fraction
        x = start[0] + fraction * (end[0] - start[0])
        y = start[1] + fraction * (end[1] - start[1])
        rows.append({'frame': 5000 + index, 'time_s': 40 + index / 20,
                     'actor_id': 17, 'source': 'original_native',
                     'source_kind': 'original_native_world_vertices',
                     'body_center_xy_m': [x, y],
                     'body_xy_m': [[x - 0.1, y - 0.1], [x + 0.1, y - 0.1],
                                   [x + 0.1, y + 0.1], [x - 0.1, y + 0.1]]})
    return rows


def prove():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        case_id = entry['case_id']
        name = case_id.rsplit('__', 1)[1]
        scene = json.loads((ROOT / 'cases' / name / 'scene.json').read_text())
        fixtures = []
        for kind, rows in [('complete_motion', body_rows(scene, 1.0)),
                           ('incomplete_motion', body_rows(scene, 0.5)),
                           ('missing_evidence', None)]:
            result = evaluate_crossing_completion(scene, rows)
            result.update(case_id=case_id, provenance_kind='synthetic_fixture',
                          diagnostic_fixture=True, physical_acceptance_claimed=False,
                          legal_acceptance_claimed=False)
            result_path = ROOT / 'cases' / name / ('physical-' + kind + '.json')
            write(result_path, result)
            command = f'.venv-cpu/bin/python work/{ROOT.name}/prove_physical_preparation.py --case {case_id} --kind {kind}'
            run = subprocess.run([sys.executable, str(ROOT / 'prove_physical_preparation.py'),
                                  '--case', case_id, '--kind', kind],
                                 cwd=ROOT.parents[1], env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                                 capture_output=True, text=True, check=True)
            log_path = ROOT / 'cases' / name / ('physical-' + kind + '.log')
            log_path.write_text(run.stdout)
            fixtures.append({'kind': kind, 'command': command,
                             'exit_code': 0, 'log': f'cases/{name}/{log_path.name}',
                             'log_sha256': sha(log_path),
                             'result': f'cases/{name}/{result_path.name}',
                             'result_sha256': sha(result_path)})
        assert [f['kind'] for f in fixtures] == ['complete_motion', 'incomplete_motion', 'missing_evidence']
        lifecycle_path = ROOT / 'cases' / name / 'physical-lifecycle.log'
        lifecycle_path.write_text('\n'.join(EVENTS) + '\n')
        receipt = {'format': 'c227749-physical-preparation-fixture',
                   'case_id': case_id,
                   'construction_sha256': entry['construction_sha256'],
                   'scope': 'synthetic CPU fixtures; Native motion, image visibility and legal acceptance unverified',
                   'fixtures': fixtures,
                   'lifecycle': {'events': EVENTS, 'exit_code': 0,
                                 'log': f'cases/{name}/{lifecycle_path.name}',
                                 'log_sha256': sha(lifecycle_path)}}
        receipt_path = ROOT / 'cases' / name / 'physical-preparation.json'
        write(receipt_path, receipt)
        entry['physical_preparation'] = {'receipt': f'cases/{name}/{receipt_path.name}',
                                         'sha256': sha(receipt_path)}
    write(ROOT / 'execution-manifest.json', manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case')
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'))
    args = parser.parse_args()
    if args.case or args.kind:
        if not args.case or not args.kind:
            parser.error('--case and --kind must be used together')
        scene_name = args.case.rsplit('__', 1)[1]
        scene = json.loads((ROOT / 'cases' / scene_name / 'scene.json').read_text())
        rows = None if args.kind == 'missing_evidence' else body_rows(scene, 1.0 if args.kind == 'complete_motion' else 0.5)
        actual = evaluate_crossing_completion(scene, rows)
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[args.kind]
        assert actual['physical_checks']['maneuver']['status'] == expected
        assert actual['maneuver_completed'] == (expected == 'met')
        print(f'{args.kind}: {expected}; synthetic fixture only')
    else:
        prove()
