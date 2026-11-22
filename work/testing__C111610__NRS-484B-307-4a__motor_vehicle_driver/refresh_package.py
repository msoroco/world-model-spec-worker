"""Refresh exact offline and physical CPU proofs after authored source changes."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args):
    subprocess.run([str(PYTHON), *map(str, args)], cwd=REPO, check=True)


def main():
    for author in ('construction_author.py', 'fallback_author.py',
                   'semantic_author.py', 'diagnostic_author.py'):
        run(ROOT / author)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate, holder in [('primary', entry),
                                   ('fallback1', entry['candidates'][0])]:
            output = REPO / '.runtime-work' / ('c111610-offline-' + suffix + '-' + candidate + '-refresh')
            if output.exists():
                import shutil
                shutil.rmtree(output)
            command = [str(PYTHON), str(REPO / 'runtime.py'), 'offline',
                '--manifest', str(MANIFEST), '--case', entry['case_id'],
                '--output', str(output), '--python', str(PYTHON),
                '--candidate', candidate]
            subprocess.run(command, cwd=REPO, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log = ROOT / ('proof-' + suffix + '-' + candidate + '.log')
            log.write_bytes((output / 'offline.log').read_bytes())
            holder['offline'] = {'command': ' '.join(command), 'exit_code': 0,
                'construction_sha256': holder['construction_sha256'],
                'log': log.name, 'log_sha256': sha(log)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    run(ROOT / 'refresh_physical.py')
    print('Exact primary and fallback offline proofs plus physical proofs refreshed.')


if __name__ == '__main__':
    main()
