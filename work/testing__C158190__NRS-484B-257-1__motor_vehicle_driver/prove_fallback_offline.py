"""Run each fallback's exact materialized construction checks and bind logs."""

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
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in entry['candidates']:
            ident = candidate['id']
            output = REPO / '.runtime-work' / f'c158190-{suffix}-{ident}-offline-v1'
            command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                       'offline', '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', ident, '--output', str(output)]
            result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
            log = ROOT / candidate['construction']
            log = log.parent / f'{ident}-offline.log'
            source_log = output / 'offline.log'
            if source_log.is_file():
                shutil.copyfile(source_log, log)
            else:
                log.write_text(result.stdout + result.stderr)
            print(json.dumps({'case': suffix, 'candidate': ident,
                              'exit_code': result.returncode,
                              'offline_log': str(log.relative_to(ROOT))}), flush=True)
            if result.returncode:
                raise ValueError(result.stdout + result.stderr)
            candidate['offline'] = {
                'command': ' '.join(Path(x).relative_to(REPO).as_posix()
                                    if x.startswith(str(REPO) + '/') else x for x in command),
                'exit_code': 0,
                'log': str(log.relative_to(ROOT)),
                'log_sha256': sha(log),
                'construction_sha256': candidate['construction_sha256'],
            }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
