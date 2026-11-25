"""Run recorded-only saved processing for twelve selected diagnostic acquisitions."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
MANIFEST = FOLDER/'execution-manifest.json'
SCRATCH = REPO/'.runtime-work'/'c124163-saved-v8'
CONDITIONS = ('other_long', 'other_at', 'other_short',
              'district_long', 'district_at', 'district_short')


def run(item):
    condition, candidate = item
    case = FOLDER.name+'__'+condition
    source = REPO/'.runtime-work'/f'c124163-compat-{condition}-{candidate}-v8'
    attempt = SCRATCH/f'sealed-{condition}-{candidate}'
    output = SCRATCH/f'derived-{condition}-{candidate}'
    if attempt.exists() or output.exists():
        raise ValueError('Retain prior saved proof: '+condition+' '+candidate)
    shutil.copytree(source, attempt)
    selection_path = attempt/'candidate-selection.json'
    selection = json.loads(selection_path.read_text())
    selection['manifest_sha256'] = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    selection_path.write_text(json.dumps(selection, indent=2)+'\n')
    cmd = [sys.executable, str(REPO/'runtime.py'), 'process-saved',
           '--manifest', str(MANIFEST), '--case', case,
           '--attempt', str(attempt), '--output', str(output),
           '--library', str(REPO/'runtime/library'),
           '--validator', str(REPO/'.runtime-work/c230328-decoder/.lake/build/bin/adapterCheck')]
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO/'.runtime-work/c124163-saved-output')
    env['TMPDIR'] = str(REPO/'.runtime-work')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    completed = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True)
    (SCRATCH/f'{condition}-{candidate}-command.log').write_text(
        (completed.stdout+completed.stderr).rstrip()+'\n')
    receipt = output/'v0001/processing.json'
    if completed.returncode or not receipt.is_file():
        raise ValueError('Saved processing failed: '+condition+' '+candidate+' '+
                         (completed.stdout+completed.stderr)[-1500:])
    proof = json.loads(receipt.read_text())
    if not (proof['passed'] and proof['recorded_only'] and proof['originals_preserved']
            and not proof['missing_evidence']):
        raise ValueError('Saved proof incomplete: '+condition+' '+candidate)
    return condition, candidate, proof['passed']


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    items = [(c, k) for c in CONDITIONS for k in ('primary', 'fallback1')]
    with ThreadPoolExecutor(max_workers=2) as executor:
        for future in as_completed([executor.submit(run, item) for item in items]):
            print(json.dumps(future.result()), flush=True)

if __name__ == '__main__':
    main()
