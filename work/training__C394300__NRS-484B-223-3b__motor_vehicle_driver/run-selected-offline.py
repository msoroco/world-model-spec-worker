"""Run current-runtime offline checks for the selected distance probes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c3943003b-selected-offline'
CASES = ('witness_1', 'witness_2', 'numeric_1_0', 'numeric_1_1', 'numeric_1_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(text):
    return '\n'.join(line.rstrip() for line in text.splitlines()).rstrip() + '\n'


def main():
    manifest = HERE / 'selected-probe-manifest.json'
    entries = {e['case_id'].rsplit('__', 1)[-1]: e for e in json.loads(manifest.read_text())['cases']}
    output = []
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        entry = entries[case]
        for candidate in CANDIDATES:
            ref = entry if candidate == 'primary' else next(c for c in entry['candidates'] if c['id'] == candidate)
            construction = HERE / ref['construction']
            assert sha(construction) == ref['construction_sha256']
            destination = SCRATCH / f'{case}-{candidate}-{sha(construction)[:12]}'
            cmd = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'), 'offline',
                   '--manifest', str(manifest), '--case', entry['case_id'],
                   '--candidate', candidate, '--output', str(destination),
                   '--python', str(ROOT / '.venv-cpu/bin/python')]
            env = os.environ.copy()
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            env['TMPDIR'] = str(ROOT / '.runtime-work')
            env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH)
            run = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
            log = HERE / 'selected-offline' / f'{case}-{candidate}.log'
            log.parent.mkdir(parents=True, exist_ok=True)
            raw = destination / 'offline.log'
            log.write_text(clean(raw.read_text() if raw.exists() else run.stdout + run.stderr))
            receipt = {'case_id': entry['case_id'], 'candidate_id': candidate,
                       'construction_sha256': sha(construction), 'command': ' '.join(cmd),
                       'exit_code': run.returncode, 'log': log.relative_to(HERE).as_posix(),
                       'log_sha256': sha(log)}
            output.append(receipt)
            print(case, candidate, run.returncode, flush=True)
            if run.returncode:
                break
        if output[-1]['exit_code']:
            break
    path = HERE / 'selected-offline-summary.json'
    path.write_text(json.dumps({'format': 'selected-offline-proof-v1', 'receipts': output}, indent=2) + '\n')
    return 0 if len(output) == len(CASES) * len(CANDIDATES) and all(r['exit_code'] == 0 for r in output) else 1


if __name__ == '__main__':
    sys.exit(main())
