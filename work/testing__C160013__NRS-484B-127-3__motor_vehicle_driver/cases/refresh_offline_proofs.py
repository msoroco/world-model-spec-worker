"""Rebuild changed inline sources and rerun all selected offline proofs."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    previous = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    subprocess.run([sys.executable, str(PACKAGE / 'cases/build_constructions.py')],
                   cwd=REPO, env=env, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(PACKAGE / 'cases/stamp_compatibility_inputs.py')],
                   cwd=REPO, env=env, check=True)
    manifest = json.loads(MANIFEST.read_text())
    manifest['comparisons'] = previous['comparisons']
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1'):
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            stage = REPO / '.runtime-work' / ('c160013-offline-v11-' + suffix + '-' + candidate)
            relative_log = 'cases/' + suffix + '-' + candidate + '-offline.log'
            log = PACKAGE / relative_log
            args = [sys.executable, str(REPO / 'runtime.py'), 'offline', '--manifest', str(MANIFEST),
                    '--case', entry['case_id'], '--candidate', candidate,
                    '--output', str(stage), '--python', sys.executable]
            with log.open('w') as stream:
                result = subprocess.run(args, cwd=REPO, env=env, stdout=stream,
                                        stderr=subprocess.STDOUT, check=False)
            if result.returncode:
                raise RuntimeError('Offline proof failed: ' + relative_log + '\n' + log.read_text()[-1000:])
            selected['offline'] = {'command': ' '.join(args),
                                   'construction_sha256': selected['construction_sha256'],
                                   'exit_code': 0, 'log': relative_log, 'log_sha256': sha(log)}
            MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print('Refreshed four primary/fallback offline proofs')


if __name__ == '__main__':
    run()
