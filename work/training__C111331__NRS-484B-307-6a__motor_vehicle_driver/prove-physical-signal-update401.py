"""Bind three CPU motion fixtures and lifecycle proof to each selected case."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        folder = HERE / 'update401-physical' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
            result = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = [sys.executable, str(HERE / 'run-physical-signal-mock-update401.py'),
                       '--case', suffix, '--kind', kind, '--output', str(result)]
            with log.open('w') as stream:
                run = subprocess.run(command, cwd=ROOT, stdout=stream,
                                     stderr=subprocess.STDOUT, timeout=30)
            if run.returncode:
                raise RuntimeError(kind + ' failed: ' + log.read_text()[-1000:])
            item = {'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                    'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                    'result': str(result.relative_to(HERE)), 'result_sha256': sha(result)}
            fixtures.append(item)
        lifecycle = fixtures.pop()
        lifecycle_result = json.loads((HERE / lifecycle['result']).read_text())
        proof = {'format': 'c111331-physical-preparation-cpu-v1',
                 'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'cpu_fixture_mock': True, 'fixtures': fixtures,
                 'lifecycle': {'events': lifecycle_result['events'], 'exit_code': 0,
                               'log': lifecycle['log'], 'log_sha256': lifecycle['log_sha256']},
                 'original_native_and_pixels_verified': False}
        receipt = folder / 'proof.json'
        receipt.write_text(json.dumps(proof, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': str(receipt.relative_to(HERE)),
                                         'sha256': sha(receipt)}
        print(suffix, 'three physical branches and lifecycle passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
