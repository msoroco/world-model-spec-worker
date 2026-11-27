"""Prove seven selected taxi/passenger/freight cases from saved CPU sources."""
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(entry, negative):
    case = entry['case_id']
    suffix = case.rsplit('__', 1)[1]
    source = SCRATCH / f'selected-fixture-{suffix}-v21'
    if not source.is_dir():
        raise ValueError('Missing current selected fixture: ' + suffix)
    label = suffix + ('-negative' if negative else '-positive')
    attempt = SCRATCH / f'saved-{label}-v24-attempt'
    if attempt.exists():
        raise ValueError('Fresh saved attempt required: ' + label)
    shutil.copytree(source, attempt)
    construction_path = PACKAGE / entry['construction']
    if sha(construction_path) != entry['construction_sha256']:
        raise ValueError('Selected construction changed: ' + suffix)
    selected = json.loads(construction_path.read_text())
    (attempt / 'construction.json').write_bytes(construction_path.read_bytes())
    for item in selected['files']:
        path = attempt / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'])
    if negative:
        remove = ('freight-purpose-review.json' if suffix.startswith('freight_')
                  else 'observed-passenger-activity.jsonl')
        (attempt / remove).unlink()
    selection = {'format': 'worker-candidate-selection',
                 'case_id': case, 'candidate_id': 'primary',
                 'construction_sha256': entry['construction_sha256'],
                 'manifest_sha256': sha(MANIFEST)}
    (attempt / 'candidate-selection.json').write_text(json.dumps(selection, indent=2) + '\n')
    return label, attempt


def prove(task):
    entry, negative = task
    label, attempt = prepare(entry, negative)
    output = SCRATCH / f'saved-{label}-v24-output'
    if output.exists():
        raise ValueError('Fresh saved output required: ' + label)
    env = os.environ.copy()
    env['TMPDIR'] = str(ROOT / '.runtime-work')
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work' / ('c150173-saved-' + label + '-v24'))
    command = [sys.executable, '-B', str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', entry['case_id'],
               '--attempt', str(attempt), '--output', str(output),
               '--library', str(ROOT / 'runtime/library'), '--validator', str(VALIDATOR)]
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    (SCRATCH / f'saved-{label}-v24.log').write_text(result.stdout + result.stderr)
    return label, result.returncode, (result.stdout + result.stderr)[-240:]


def main():
    entries = [entry for entry in json.loads(MANIFEST.read_text())['cases']
               if entry['case_id'].rsplit('__', 1)[1].startswith('freight_')]
    tasks = [(entry, negative) for entry in entries for negative in (False, True)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for label, code, tail in pool.map(prove, tasks):
            print(label, code, tail.replace('\n', ' '), flush=True)
            if code:
                raise SystemExit(code)


if __name__ == '__main__':
    main()
