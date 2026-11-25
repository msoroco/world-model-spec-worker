"""Verify missing original history gives recorded-only feedback without replay."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__public_park_attended'
SOURCE = REPO / '.runtime-work/c150099-saved-negative-source-v3'
FIXTURE = REPO / '.runtime-work/c150099-saved-negative-fixture-v3'
OUTPUT = REPO / '.runtime-work/c150099-saved-negative-output-v3'


def run(*args) -> None:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(REPO / '.runtime-work'))
    completed = subprocess.run([str(REPO / '.venv-cpu/bin/python'),
                                str(REPO / 'runtime.py'), *map(str, args)],
                               cwd=REPO, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode:
        raise ValueError(completed.stdout[-1600:])


def main() -> None:
    for path in (SOURCE, FIXTURE, OUTPUT):
        if path.exists():
            raise ValueError('retain prior negative; choose new proof version')
    manifest = ROOT / 'execution-manifest.json'
    run('materialize', '--manifest', manifest, '--case', CASE, '--output', SOURCE)
    run('fixture', '--recipe', ROOT / 'diagnostic-public_park_attended-recipe.json',
        '--output', FIXTURE)
    for path in FIXTURE.iterdir():
        destination = SOURCE / path.name
        if destination.exists():
            raise ValueError('fixture shadows package')
        if path.is_dir():
            shutil.copytree(path, destination)
        else:
            shutil.copy2(path, destination)
    (SOURCE / 'original-attempt/history.jsonl').unlink()
    run('process-saved', '--manifest', manifest, '--case', CASE,
        '--attempt', SOURCE, '--output', OUTPUT, '--library', REPO / 'runtime/library',
        '--validator', REPO / '.runtime-work/c150099-decoder-v2/.lake/build/bin/adapterCheck')
    version = OUTPUT / 'v0001'
    feedback = json.loads((version / 'feedback.json').read_text())
    proof = json.loads((version / 'processing.json').read_text())
    if (feedback.get('recorded_only') is not True or
            feedback.get('native_replay_requested') is not False or
            'Missing required source: original-attempt/history.jsonl' not in
            feedback.get('error', '') or proof.get('missing_evidence') is not True):
        raise ValueError('missing-source saved feedback did not fail closed')
    receipt = {'format': 'worker-saved-negative-diagnostic', 'case_id': CASE,
               'missing_source': 'original-attempt/history.jsonl',
               'recorded_only': True, 'native_replay_requested': False,
               'physical_acceptance_claimed': False,
               'feedback_sha256': hashlib.sha256((version / 'feedback.json').read_bytes()).hexdigest(),
               'processing_sha256': hashlib.sha256((version / 'processing.json').read_bytes()).hexdigest()}
    (ROOT / 'cpu-saved-negative.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print('saved missing-source negative passed')


if __name__ == '__main__':
    main()
