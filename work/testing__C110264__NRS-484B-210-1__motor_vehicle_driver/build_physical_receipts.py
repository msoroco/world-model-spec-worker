"""Bind executed source-shaped physical outcome and lifecycle CPU proofs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            log = f'cpu-physical-{suffix}-{kind}.log'
            result = f'physical-{suffix}-{kind}.json'
            data = json.loads((HERE / result).read_text())
            status = data['physical_checks']['maneuver']['status']
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            if status != expected:
                raise ValueError('physical outcome fixture differs: ' + kind)
            fixtures.append({
                'kind': kind,
                'command': (f'.venv-cpu/bin/python work/{HERE.name}/prove_physical.py '
                            f'--case {entry["case_id"]} --kind {kind} '
                            f'--scratch .runtime-work/c110264-output/physical '
                            f'--result work/{HERE.name}/{result}'),
                'exit_code': 0, 'log': log, 'log_sha256': sha(HERE / log),
                'result': result, 'result_sha256': sha(HERE / result)})
        lifecycle = 'cpu-physical-lifecycle.log'
        proof = {
            'format': 'worker-physical-preparation',
            'case_id': entry['case_id'],
            'construction_sha256': entry['construction_sha256'],
            'fixtures': fixtures,
            'lifecycle': {
                'events': ['capture_finished', 'encoders_closed',
                           'restoration_verified', 'native_exit',
                           'owner_released', 'saved_processing_started'],
                'command': (f'.venv-cpu/bin/python -m unittest discover -s '
                            f'work/{HERE.name}/tests -p test_pass_right_lifecycle.py -v'),
                'exit_code': 0, 'log': lifecycle,
                'log_sha256': sha(HERE / lifecycle),
                'scope': 'diagnostic ordering test; local owner release remains to be observed'}}
        path = HERE / f'physical-preparation-{suffix}.json'
        path.write_text(json.dumps(proof, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': path.name, 'sha256': sha(path)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
