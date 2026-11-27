"""Run exact red-curb offline and source-bound compatibility CPU proofs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from red_curb import CASES
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work' / 'c229452-proofs-v1'
MANIFEST = ROOT / 'execution-manifest.json'
PYTHON = REPO / '.venv-cpu/bin/python'
RUNTIME = REPO / 'runtime.py'
LIBRARY = REPO / 'runtime/library'
VALIDATOR = REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def clean_output(data):
    return data.rstrip() + '\n' if data.strip() else ''


def run_case(case, candidate):
    short = case.name + '-' + candidate
    folder = SCRATCH / short
    folder.mkdir(parents=True, exist_ok=True)
    cid = ASSIGNMENT + '__' + case.name
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               TMPDIR=str(REPO / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c229452-pipeline-output'),
               MPLCONFIGDIR=str(REPO / '.runtime-work/mpl-cache'))
    offline_command = [str(PYTHON), str(RUNTIME), 'offline',
                       '--manifest', str(MANIFEST), '--case', cid,
                       '--candidate', candidate, '--output', str(folder / 'offline'),
                       '--python', str(PYTHON)]
    offline = subprocess.run(offline_command, cwd=REPO, env=env,
                             capture_output=True, text=True)
    (ROOT / ('cpu-offline-' + short + '.log')).write_text(clean_output(offline.stdout + offline.stderr))
    if offline.returncode:
        return (short, 'offline', offline.returncode)
    raw = (folder / 'offline/offline.log').read_text()
    (ROOT / ('cpu-offline-detail-' + short + '.log')).write_text(clean_output(raw))
    compatibility_command = [str(PYTHON), str(RUNTIME), 'compatibility',
                             '--manifest', str(MANIFEST), '--case', cid,
                             '--candidate', candidate, '--output', str(folder / 'compat'),
                             '--library', str(LIBRARY), '--validator', str(VALIDATOR)]
    compatibility = subprocess.run(compatibility_command, cwd=REPO, env=env,
                                   capture_output=True, text=True)
    (ROOT / ('cpu-compatibility-' + short + '.log')).write_text(
        clean_output(compatibility.stdout + compatibility.stderr))
    if compatibility.returncode:
        return (short, 'compatibility', compatibility.returncode)
    source = folder / 'compat'
    for original, target in (
            ('compatibility.json', 'cpu-compatibility-' + short + '.json'),
            ('compatibility-analysis.log', 'cpu-compatibility-analysis-' + short + '.log'),
            ('negative-analysis.log', 'cpu-compatibility-negative-' + short + '.log')):
        shutil.copyfile(source / original, ROOT / target)
    return (short, 'passed', 0)


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (REPO / '.runtime-work/c229452-pipeline-output').mkdir(parents=True, exist_ok=True)
    (REPO / '.runtime-work/mpl-cache').mkdir(parents=True, exist_ok=True)
    tasks = [(case, candidate) for case in CASES for candidate in ('primary', 'fallback1')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(run_case, case, candidate): (case.name, candidate)
                   for case, candidate in tasks}
        failures = []
        for future in as_completed(futures):
            result = future.result()
            print(*result, flush=True)
            if result[-1]:
                failures.append(result)
    if failures:
        print(json.dumps({'failures': failures}, indent=2))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
