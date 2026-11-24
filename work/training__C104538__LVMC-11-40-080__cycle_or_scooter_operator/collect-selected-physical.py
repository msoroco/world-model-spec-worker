"""Retain exact positive, incomplete, missing-source, and lifecycle CPU proofs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result_path = folder / (kind + '.json')
            command = [sys.executable, str(HERE / 'prove-selected-physical.py'),
                       '--case', suffix, '--kind', kind, '--output', str(result_path)]
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            log = folder / (kind + '.log')
            log.write_text(run.stdout.rstrip() + '\n' if run.returncode == 0 else run.stderr.rstrip() + '\n')
            if run.returncode:
                raise RuntimeError(log.read_text())
            fixtures.append({'kind': kind,
                             'command': f'.venv-cpu/bin/python work/{HERE.name}/prove-selected-physical.py --case {suffix} --kind {kind} --output work/{HERE.name}/physical-proof/{suffix}/{kind}.json',
                             'exit_code': run.returncode,
                             'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                             'result': str(result_path.relative_to(HERE)),
                             'result_sha256': sha(result_path)})
        command = [sys.executable, str(HERE / 'prove-selected-physical.py'),
                   '--case', suffix, '--kind', 'lifecycle']
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = folder / 'lifecycle.log'
        log.write_text(run.stdout.rstrip() + '\n' if run.returncode == 0 else run.stderr.rstrip() + '\n')
        if run.returncode:
            raise RuntimeError(log.read_text())
        lifecycle = json.loads(run.stdout)
        lifecycle.update({'exit_code': 0, 'log': str(log.relative_to(HERE)),
                          'log_sha256': sha(log)})
        proof = {'format': 'c104538-rider-physical-preparation-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'scope': 'synthetic CPU outcome and sequencing only; Native physical capture pending',
                 'fixtures': fixtures, 'lifecycle': lifecycle}
        target = folder / 'proof.json'
        write(target, proof)
        entry['physical_preparation'] = {'receipt': str(target.relative_to(HERE)),
                                         'sha256': sha(target)}
    write(manifest_path, manifest)
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
