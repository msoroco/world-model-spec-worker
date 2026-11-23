"""Refresh exact offline receipts after source-bound draft changes."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'draft-primary-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    manifest = json.loads(MANIFEST.read_text())
    successes = 0
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in [{'id': 'primary', 'construction_sha256': entry['construction_sha256']},
                          *entry['candidates']]:
            ident = candidate['id']
            version = 5
            while (ROOT / '.runtime-work' /
                   ('c229398-offline-v' + str(version) + '-' + suffix + '-' + ident)).exists():
                version += 1
            output = ROOT / '.runtime-work' / (
                'c229398-offline-v' + str(version) + '-' + suffix + '-' + ident)
            log = PACKAGE / 'draft-offline-logs' / suffix / (ident + '.log')
            log.parent.mkdir(parents=True, exist_ok=True)
            command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                       'offline', '--manifest', str(MANIFEST.relative_to(ROOT)),
                       '--case', entry['case_id'], '--candidate', ident,
                       '--output', str(output.relative_to(ROOT))]
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=360)
            if result.returncode:
                raise ValueError('Offline failed: ' + str(log))
            offline = {
                'command': ' '.join(command), 'exit_code': 0,
                'construction_sha256': candidate['construction_sha256'],
                'log': str(log.relative_to(PACKAGE)), 'log_sha256': sha(log)}
            if ident == 'primary':
                entry['offline'] = offline
            else:
                candidate['offline'] = offline
            successes += 1
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'offline_passed': successes, 'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    run()
