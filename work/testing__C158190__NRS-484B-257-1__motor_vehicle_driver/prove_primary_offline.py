"""Refresh exact primary offline checks after an inline construction change."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__yield_nearest_view_', 1)[-1]
        output = REPO / '.runtime-work' / f'c158190-{suffix}-primary-offline-v4'
        command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                   'offline', '--manifest', str(MANIFEST), '--case', entry['case_id'],
                   '--output', str(output)]
        result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        folder = (ROOT / entry['construction']).parent
        log = folder / 'primary-offline-current.log'
        source = output / 'offline.log'
        log.write_bytes(source.read_bytes()) if source.is_file() else log.write_text(result.stdout + result.stderr)
        if result.returncode:
            raise ValueError(f'{suffix}: primary offline failed: {result.stdout[-1000:]} {result.stderr[-1000:]}')
        entry['offline'] = {
            'command': ' '.join(Path(arg).relative_to(REPO).as_posix()
                                if arg.startswith(str(REPO) + '/') else arg for arg in command),
            'exit_code': 0, 'log': str(log.relative_to(ROOT)),
            'log_sha256': sha(log), 'construction_sha256': entry['construction_sha256'],
        }
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({'case': suffix, 'offline_passed': True}), flush=True)


if __name__ == '__main__':
    main()
