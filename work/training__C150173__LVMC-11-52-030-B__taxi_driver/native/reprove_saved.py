"""Rebind source-shaped saved-only fixtures to current selected constructions."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c150173-owner'
MANIFEST = PACKAGE / 'selected-draft-manifest.json'
VALIDATOR = SCRATCH / 'decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(suffix, negative, entry):
    old = SCRATCH / (f'saved-{suffix}-v13-'
                     + ('negative-' if negative else '') + 'attempt')
    if suffix == 'probe_a':
        old = SCRATCH / ('saved-attempt-probe_a-v13' + ('-negative' if negative else ''))
    if not old.is_dir():
        raise ValueError('Missing retained source-shaped fixture: ' + str(old))
    label = suffix + ('-negative' if negative else '-positive')
    attempt = SCRATCH / f'saved-{label}-v15-attempt'
    if attempt.exists():
        raise ValueError('Use fresh saved fixture directory: ' + str(attempt))
    shutil.copytree(old, attempt)
    construction = PACKAGE / entry['construction']
    selected = json.loads(construction.read_text())
    if sha(construction) != entry['construction_sha256']:
        raise ValueError('Selected construction changed')
    (attempt / 'construction.json').write_bytes(construction.read_bytes())
    for item in selected['files']:
        path = attempt / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'])
    selection = {
        'format': 'worker-candidate-selection',
        'case_id': entry['case_id'], 'candidate_id': 'primary',
        'construction_sha256': entry['construction_sha256'],
        'manifest_sha256': sha(MANIFEST),
    }
    (attempt / 'candidate-selection.json').write_text(json.dumps(selection, indent=2) + '\n')
    return label, attempt


def prove(args):
    suffix, negative, entry = args
    label, attempt = prepare(suffix, negative, entry)
    output = SCRATCH / f'saved-{label}-v15-output'
    if output.exists():
        raise ValueError('Use fresh saved output directory: ' + str(output))
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work' / ('c150173-saved-output-' + label))
    command = [sys.executable, '-B', str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', entry['case_id'],
               '--attempt', str(attempt), '--output', str(output),
               '--library', str(ROOT / 'runtime/library'), '--validator', str(VALIDATOR)]
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    (SCRATCH / f'saved-{label}-v15.log').write_text(result.stdout + result.stderr)
    return label, result.returncode, (result.stdout + result.stderr)[-300:]


def main():
    entries = json.loads(MANIFEST.read_text())['cases']
    tasks = [(item['case_id'].rsplit('__', 1)[1], negative, item)
             for item in entries for negative in (False, True)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for label, code, tail in pool.map(prove, tasks):
            print(label, code, tail.replace('\n', ' '), flush=True)
            if code:
                raise SystemExit(code)


if __name__ == '__main__':
    main()
