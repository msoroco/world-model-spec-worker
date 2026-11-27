"""Replay selected saved acquisition only, using scratch copies of diagnostics."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name


def run(slug):
    origin = REPO / '.runtime-work' / ('c146108-compat7-' + slug)
    attempt = REPO / '.runtime-work' / ('c146108-saved7-attempt6-' + slug)
    output = REPO / '.runtime-work' / ('c146108-saved7-' + slug)
    if attempt.exists() or output.exists():
        raise ValueError('Retain prior saved attempt; use fresh scratch names')
    shutil.copytree(origin, attempt)
    (attempt / 'candidate-selection.json').unlink()
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c146108-owner')
    env['TMPDIR'] = str(REPO / '.runtime-work')
    command = [sys.executable, '-B', str(REPO / 'runtime.py'), 'process-saved',
        '--manifest', str(HERE / 'draft-native-manifest.json'), '--case', AID + '__' + slug,
        '--attempt', str(attempt), '--output', str(output), '--library', str(REPO / 'runtime/library'),
        '--validator', str(REPO / '.runtime-work/c386328-decoder/.lake/build/bin/adapterCheck')]
    completed = subprocess.run(command, cwd=REPO, env=env,
        stdout=output.with_suffix('.log').open('w'), stderr=subprocess.STDOUT, timeout=900)
    return completed.returncode


if __name__ == '__main__':
    print(run(sys.argv[1]))
