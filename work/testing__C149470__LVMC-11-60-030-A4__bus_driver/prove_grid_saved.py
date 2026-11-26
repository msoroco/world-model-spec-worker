"""Pinned recorded-only processing of 13 retained synthetic software fixtures."""
import os
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor

from bus_curb import CASES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = ROOT / '.venv-cpu/bin/python'
MANIFEST = HERE / 'execution-manifest.compatibility-diagnostic.json'
DECODER = ROOT / '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'


def process(case):
    cid = HERE.name + '__' + case.name
    attempt = ROOT / '.runtime-work/c149470' / ('grid9-compat-' + case.name)
    output = ROOT / '.runtime-work/c149470' / ('grid9-saved-' + case.name)
    command = [str(PYTHON), 'runtime.py', 'process-saved', '--manifest', str(MANIFEST),
               '--case', cid, '--attempt', str(attempt), '--output', str(output),
               '--library', 'runtime/library', '--validator', str(DECODER)]
    log = HERE / ('cpu-grid-saved-' + case.name + '.log')
    with log.open('w', encoding='utf-8') as handle:
        result = subprocess.run(command, cwd=ROOT, env=os.environ.copy(),
                                stdout=handle, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f'{case.name}: saved processing failed, exit {result.returncode}')
    print('saved-only passed:', case.name, flush=True)


def main():
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(process, CASES))


if __name__ == '__main__':
    main()
