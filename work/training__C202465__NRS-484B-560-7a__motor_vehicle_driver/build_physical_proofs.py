"""Build synthetic physical/lifecycle CPU receipts without claiming Native acceptance."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        out = HERE / 'proofs' / 'physical' / suffix
        out.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in KINDS:
            result = out / (kind + '.json')
            log = out / (kind + '.log')
            cmd = [sys.executable, '-B', str(HERE / 'physical_fixture.py'),
                   '--condition', suffix, '--kind', kind, '--output', str(result)]
            run = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                                 env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            log.write_text((run.stdout + run.stderr).rstrip() + '\n')
            if run.returncode:
                raise RuntimeError(f'{suffix} {kind}: {run.stderr}')
            fixtures.append({'kind': kind, 'command': ' '.join(cmd), 'exit_code': 0,
                             'log': str(log.relative_to(HERE)), 'log_sha256': digest(log),
                             'result': str(result.relative_to(HERE)), 'result_sha256': digest(result)})
        life = out / 'lifecycle.log'
        result = out / 'lifecycle.json'
        cmd = [sys.executable, '-B', str(HERE / 'physical_fixture.py'),
               '--condition', suffix, '--kind', 'lifecycle', '--output', str(result)]
        run = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                             env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        life.write_text((run.stdout + run.stderr).rstrip() + '\n')
        if run.returncode:
            raise RuntimeError(f'{suffix} lifecycle: {run.stderr}')
        events = json.loads(result.read_text())['events']
        proof = {'format': 'c202465-cpu-physical-preparation-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures,
                 'lifecycle': {'events': events, 'exit_code': 0,
                               'log': str(life.relative_to(HERE)), 'log_sha256': digest(life)},
                 'original_native_executed': False, 'physical_completion_claimed': False}
        write(out / 'proof.json', proof)
        print(suffix, digest(out / 'proof.json'))


if __name__ == '__main__':
    main()
