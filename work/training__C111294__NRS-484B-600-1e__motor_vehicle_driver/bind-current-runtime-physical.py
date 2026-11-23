"""Bind four independent speed-completion and lifecycle CPU mock proofs."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.physical_preparation import validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main(tag):
    manifest_path = HERE / 'current-runtime-reproof-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if len(manifest['cases']) != 4:
        raise ValueError('Four exact selected boundary cases required')
    for case in manifest['cases']:
        suffix = case['case_id'].removeprefix(HERE.name + '__')
        folder = HERE / f'{tag}-selected-physical' / suffix
        if folder.exists():
            raise ValueError('Retain prior physical proof: ' + str(folder))
        fixtures = []
        lifecycle = None
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
            result_path = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, str(HERE / 'run-current-runtime-physical-mock.py'),
                       '--case', suffix, '--kind', kind, '--output', str(result_path)]
            run = subprocess.run(command, cwd=ROOT, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
            folder.mkdir(parents=True, exist_ok=True)
            log.write_text(run.stdout)
            if run.returncode or not result_path.is_file():
                raise ValueError('Physical CPU mock failed: ' + suffix + '/' + kind + ': ' + run.stdout)
            result = json.loads(result_path.read_text())
            if (result.get('cpu_fixture_mock') is not True or
                    result.get('original_native_motion_verified') is not False or
                    result['construction_sha256'] != case['construction_sha256']):
                raise ValueError('Physical mock identity or provenance differs')
            if kind == 'lifecycle':
                lifecycle = {'events': result['events'], 'exit_code': 0,
                             'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log)}
            else:
                fixtures.append({'kind': kind, 'command': ' '.join(command),
                                 'exit_code': 0, 'log': log.relative_to(HERE).as_posix(),
                                 'log_sha256': sha(log),
                                 'result': result_path.relative_to(HERE).as_posix(),
                                 'result_sha256': sha(result_path)})
        receipt = folder / 'proof.json'
        save(receipt, {'format': 'c111294-selected-physical-cpu-v1',
                       'case_id': case['case_id'],
                       'construction_sha256': case['construction_sha256'],
                       'fixtures_are_cpu_mocks': True,
                       'original_native_motion_verified': False,
                       'fixtures': fixtures, 'lifecycle': lifecycle})
        spec = {'receipt': receipt.relative_to(HERE).as_posix(), 'sha256': sha(receipt)}
        validate(ROOT, HERE, {**case, 'physical_preparation': spec})
        case['physical_preparation'] = spec

        print(suffix, 'three outcomes and lifecycle passed', flush=True)
    print(json.dumps({'selected_cases': 4, 'cpu_mock_outcomes': 12,
                      'lifecycle_tests': 4, 'manifest_sha256': sha(manifest_path),
                      'original_native_motion_verified': False}))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    main(parser.parse_args().tag)
