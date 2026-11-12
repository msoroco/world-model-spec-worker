"""Bind the two selected Walk cases to explicit CPU mock branch receipts."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline'))
from scenario_pipeline.worker_exchange.physical_preparation import validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    assert len(manifest['cases']) == 2
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        folder = HERE / 'update018-selected-physical' / suffix
        fixtures = []
        lifecycle = None
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
            result_path, log = folder / (kind + '.json'), folder / (kind + '.log')
            command = [sys.executable, str(HERE / 'run-selected-physical-mock.py'),
                       '--case', suffix, '--kind', kind, '--output', str(result_path)]
            run = subprocess.run(command, cwd=REPO, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(run.stdout)
            if run.returncode or not result_path.is_file():
                raise ValueError('Walk physical mock failed ' + suffix + ' ' + kind + ': ' + run.stdout)
            result = json.loads(result_path.read_text())
            if (result.get('cpu_fixture_mock') is not True or
                    result.get('original_native_motion_verified') is not False or
                    result.get('original_walk_pixels_verified') is not False or
                    result['construction_sha256'] != entry['construction_sha256']):
                raise ValueError('Walk mock provenance or construction differs')
            if kind == 'lifecycle':
                lifecycle = {'events': result['events'], 'exit_code': 0,
                             'log': str(log.relative_to(HERE)), 'log_sha256': sha(log)}
            else:
                fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                                 'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                                 'result': str(result_path.relative_to(HERE)),
                                 'result_sha256': sha(result_path)})
        proof = {'format': 'c111256-selected-physical-cpu-fixtures-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures_are_cpu_mocks': True,
                 'original_native_motion_verified': False,
                 'original_walk_pixels_verified': False,
                 'fixtures': fixtures, 'lifecycle': lifecycle}
        receipt = folder / 'proof.json'
        save(receipt, proof)
        spec = {'receipt': str(receipt.relative_to(HERE)), 'sha256': sha(receipt)}
        validate(REPO, HERE, {**entry, 'physical_preparation': spec})
        entry['physical_preparation'] = spec
    save(path, manifest)
    print(json.dumps({'selected_cases': 2, 'cpu_outcomes': 6,
                      'lifecycle_fixtures': 2, 'manifest_sha256': sha(path),
                      'original_native_motion_verified': False}))


if __name__ == '__main__':
    main()
