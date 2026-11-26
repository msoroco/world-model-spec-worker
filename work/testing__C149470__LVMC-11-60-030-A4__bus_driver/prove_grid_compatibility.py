"""Run pinned current-runtime offline and source-negative compatibility for 13 selected bundles."""
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from bus_curb import CASES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.compatibility-diagnostic.json'
DECODER = ROOT / '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'
PYTHON = ROOT / '.venv-cpu/bin/python'


def run(command, log):
    with log.open('w', encoding='utf-8') as output:
        result = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                                stdout=output, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f'{log.name}: exit {result.returncode}')


def prove(case):
        cid = HERE.name + '__' + case.name
        offline = ROOT / '.runtime-work/c149470' / ('grid9-offline-' + case.name)
        compat = ROOT / '.runtime-work/c149470' / ('grid9-compat-' + case.name)
        run([str(PYTHON), 'runtime.py', 'offline', '--manifest', str(MANIFEST),
             '--case', cid, '--output', str(offline), '--python', str(PYTHON)],
            HERE / ('cpu-grid-offline-' + case.name + '.log'))
        run([str(PYTHON), 'runtime.py', 'compatibility', '--manifest', str(MANIFEST),
             '--case', cid, '--output', str(compat), '--library', 'runtime/library',
             '--validator', str(DECODER)],
            HERE / ('cpu-grid-compat-' + case.name + '.log'))
        print('offline/compatibility passed:', case.name, flush=True)


def main():
    if not DECODER.is_file():
        raise FileNotFoundError(DECODER)
    cases = tuple(case for case in CASES if 'source_review' in case.name) + tuple(
        case for case in CASES if 'source_review' not in case.name)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(prove, cases))


if __name__ == '__main__':
    main()
