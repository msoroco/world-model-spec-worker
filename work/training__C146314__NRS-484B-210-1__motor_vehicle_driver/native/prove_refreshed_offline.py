"""Run current pinned offline tests for the selected primary and fallback bundles."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'execution-manifest.json'
LOGS = PACKAGE / 'native/scope-refresh/offline'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    passed = 0
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for candidate_id, selected in [('primary', entry)] + [
                (candidate['id'], candidate) for candidate in entry['candidates']]:
            output = REPO / '.runtime-work' / (
                'c146314-scope-' + suffix + '-' + candidate_id + '-'
                + uuid.uuid4().hex[:8])
            command = [sys.executable, str(REPO / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', candidate_id, '--output', str(output)]
            result = subprocess.run(command, cwd=REPO, capture_output=True,
                                    text=True, timeout=360, env=os.environ.copy())
            if result.returncode:
                raise RuntimeError(suffix + '/' + candidate_id + ': '
                                   + result.stdout + result.stderr)
            receipt = json.loads(result.stdout)
            if not receipt['offline_passed'] or receipt['simulation_started']:
                raise ValueError('Incomplete offline: ' + suffix + '/' + candidate_id)
            log = LOGS / (suffix + '-' + candidate_id + '.log')
            log.write_text((output / 'offline.log').read_text().rstrip() + '\n')
            selected['offline'] = {
                'command': ' '.join(command).replace(str(REPO) + '/', ''),
                'construction_sha256': selected['construction_sha256'],
                'exit_code': 0, 'log': str(log.relative_to(PACKAGE)),
                'log_sha256': sha(log)}
            MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
            passed += 1
    return passed


if __name__ == '__main__':
    print('Pinned offline proofs passed:', main())
