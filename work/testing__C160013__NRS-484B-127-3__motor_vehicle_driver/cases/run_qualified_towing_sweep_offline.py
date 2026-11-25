"""Run exact qualified sweep primary and fallback offline proofs."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'qualified-towing-sweep-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for index, entry in enumerate(manifest['cases']):
        for candidate_id, node in (('primary', entry), ('fallback1', entry['candidates'][0])):
            name = f'qualified-towing-sweep-{index}-{candidate_id}'
            output = REPO / '.runtime-work' / ('c160013-' + name + '-offline-v3')
            log = PACKAGE / 'cases' / (name + '-offline.log')
            command = [sys.executable, str(REPO / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', candidate_id, '--output', str(output),
                       '--python', sys.executable]
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=REPO, stdout=stream,
                                        stderr=subprocess.STDOUT, check=False)
            if result.returncode:
                raise RuntimeError(name + ' offline failed: ' + log.read_text()[-1600:])
            node['offline'] = {'command': ' '.join(command), 'exit_code': 0,
                               'construction_sha256': node['construction_sha256'],
                               'log': 'cases/' + log.name, 'log_sha256': sha(log)}
            print(name, 'passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
