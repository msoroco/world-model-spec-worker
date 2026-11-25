"""Run six exact selected-source offline checks using isolated scratch."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'selected-probe-manifest.json'
SCRATCH = ROOT / '.runtime-work/c394300-selected-offline'
RETURN = HERE / 'selected-offline'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    RETURN.mkdir(exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'pipeline'),
               TMPDIR=str(SCRATCH), MPLCONFIGDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE='1')
    data = json.loads(MANIFEST.read_text())
    for entry in data['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        for ident in ('primary', 'fallback1', 'fallback3'):
            selected = entry if ident == 'primary' else next(c for c in entry['candidates'] if c['id'] == ident)
            output = SCRATCH / (case + '-' + ident + '-' + selected['construction_sha256'][:12])
            command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', ident, '--output', str(output), '--python', sys.executable]
            log = RETURN / (case + '-' + ident + '.log')
            result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
            log.write_text(result.stdout.rstrip() + '\n')
            proof = {'command': ' '.join(command), 'exit_code': result.returncode,
                     'construction_sha256': selected['construction_sha256'],
                     'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log)}
            selected['offline'] = proof
            print(case, ident, result.returncode, flush=True)
            if result.returncode:
                raise SystemExit(1)
    MANIFEST.write_text(json.dumps(data, indent=2) + '\n')


if __name__ == '__main__':
    main()
