"""Bind four staged sweep cases to source-shaped physical/lifecycle CPU proofs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.physical_preparation import validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    path = HERE / 'sweep-proof-bound-promotion-candidate.json'
    manifest = json.loads(path.read_text())
    if len(manifest['cases']) != 4:
        raise ValueError('Four sweep cases required')
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        folder = HERE / 'update030-sweep-physical' / suffix
        if folder.exists():
            receipt = folder / 'proof.json'
            if not receipt.is_file():
                raise ValueError('Incomplete prior physical CPU fixture output')
            spec = {'receipt': str(receipt.relative_to(HERE)), 'sha256': sha(receipt)}
            validate(REPO, HERE, {**entry, 'physical_preparation': spec})
            entry['physical_preparation'] = spec
            continue
        fixtures = []
        lifecycle = None
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
            result_path, log = folder / (kind + '.json'), folder / (kind + '.log')
            command = [str(REPO / '.venv-cpu/bin/python'),
                       str(HERE / 'run-sweep-physical-mock.py'),
                       '--case', suffix, '--kind', kind, '--output', str(result_path)]
            run = subprocess.run(command, cwd=REPO, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(run.stdout)
            if run.returncode or not result_path.is_file():
                raise ValueError('Sweep physical mock failed ' + suffix + ' ' + kind + ': ' + run.stdout)
            result = json.loads(result_path.read_text())
            if (result.get('cpu_fixture_mock') is not True or
                    result.get('original_native_motion_verified') is not False or
                    result.get('original_walk_pixels_verified') is not False or
                    result['construction_sha256'] != entry['construction_sha256']):
                raise ValueError('Sweep mock provenance or construction differs')
            if kind == 'lifecycle':
                lifecycle = {'events': result['events'], 'exit_code': 0,
                             'log': str(log.relative_to(HERE)), 'log_sha256': sha(log)}
            else:
                fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                                 'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                                 'result': str(result_path.relative_to(HERE)),
                                 'result_sha256': sha(result_path)})
        proof = {'format': 'c111256-unselected-sweep-physical-cpu-fixtures-v1',
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
    print(json.dumps({'sweep_cases': 4, 'cpu_outcomes': 12,
                      'lifecycle_fixtures': 4, 'pinned_physical_validator': 'passed',
                      'manifest_sha256': sha(path), 'selected': False,
                      'original_native_motion_verified': False}, sort_keys=True))


if __name__ == '__main__':
    main()
