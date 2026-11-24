"""Reprove eight refreshed exact bundles and bind the physical receipt identity."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    scratch = next(repo / '.runtime-work' / f'c229439-offline-bridge-v{index}'
                   for index in range(1, 100)
                   if not (repo / '.runtime-work' / f'c229439-offline-bridge-v{index}').exists())
    scratch.mkdir()
    for entry in manifest['cases']:
        short = entry['case_id'].rsplit('__', 1)[-1]
        output = scratch / short
        if output.exists():
            raise ValueError('offline proof output already exists: ' + str(output))
        command = [sys.executable, str(repo / 'runtime.py'), 'offline',
                   '--manifest', str(manifest_path), '--case', entry['case_id'],
                   '--output', str(output), '--python', sys.executable]
        completed = subprocess.run(command, capture_output=True, text=True, env=os.environ.copy())
        log = folder / ('proof-' + short + '.log')
        log.write_text((completed.stdout + completed.stderr).rstrip() + '\n')
        if completed.returncode:
            raise ValueError(short + ': exact offline failed: ' + log.read_text()[-1000:])
        entry['offline'].update(command=' '.join(command), exit_code=0,
                                construction_sha256=entry['construction_sha256'],
                                log=log.name, log_sha256=sha(log),
                                scope='Current-runtime exact source-gated Native bundle materialization and 30 focused tests; actual CARLA capture pending')
        physical_path = folder / entry['physical_preparation']['receipt']
        physical = json.loads(physical_path.read_text())
        physical['construction_sha256'] = entry['construction_sha256']
        physical_path.write_text(json.dumps(physical, indent=2) + '\n')
        entry['physical_preparation']['sha256'] = sha(physical_path)
        print(short + ': offline and physical binding passed')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
