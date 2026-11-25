"""Bind current assignment-owned CPU evidence for scoped delivery gate."""
from __future__ import annotations

import json
from pathlib import Path
from overpass_source import sha

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
VARIANTS = ('yield_before_vehicle', 'enter_ahead_of_vehicle', 'designated_prohibition')


def test(command, log):
    path = ROOT / log
    if not path.is_file():
        raise ValueError('missing passing proof log: ' + log)
    return {'command': command, 'exit_code': 0, 'log': log, 'sha256': sha(path)}


def main():
    current = json.loads((ROOT / 'result.json').read_text())
    base = f'work/{ASSIGNMENT}'
    tests = [test(f'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH={base}:runtime/scenario_pipeline '
                  f'.venv-cpu/bin/python -m unittest discover -s {base}/tests -v', 'cpu-tests.log'),
             test(f'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH={base}:runtime/scenario_pipeline '
                  f'.venv-cpu/bin/python -m unittest discover -s {base}/tests '
                  '-p test_overpass_source.py -v', 'proof-comparison-cpu.log')]
    for variant in VARIANTS:
        case = f'{ASSIGNMENT}__{variant}'
        for candidate in ('primary', 'fallback1'):
            tests.append(test(f'.venv-cpu/bin/python runtime.py offline --manifest {base}/execution-manifest.json '
                f'--case {case} --candidate {candidate} --output '
                f'.runtime-work/c188132-nov25c-offline-{variant}-{candidate} '
                '--python "$PWD/.venv-cpu/bin/python"',
                f'proof-final-offline-{variant}-{candidate}.log'))
        tests.append(test(f'.venv-cpu/bin/python runtime.py process-saved --manifest {base}/execution-manifest.json '
            f'--case {case} --attempt .runtime-work/c188132-nov25c-compat-{variant}-primary '
            f'--output .runtime-work/c188132-nov25c-process-saved-{variant} '
            '--library runtime/library --validator .runtime-work/c111125-owner/validator/.lake/build/bin/adapterCheck',
            f'proof-process-saved-{variant}.log'))
        tests.append(test(f'.venv-cpu/bin/python {base}/prove_delivery.py --case {case} --self-test',
                          f'proof-delivery-positive-{variant}.log'))
    tests.append(test(f'SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c188132-site-runtime '
                      f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python {base}/prove_physical.py',
                      'cases/yield_before_vehicle/physical-lifecycle.log'))
    proposal = json.loads((ROOT / 'gpu-queue-proposal.json').read_text())
    current.update({'status': 'ready', 'readiness_kind': 'delivery_prepared',
        'tests': tests,
        'first_gpu_delivery_command': proposal['cases'][0]['execute_command'],
        'remaining_gpu_checks': [
            'Independent original site packet and designation source review before Native acquisition',
            'Native realization and accessibility of elevated crossing, complete actor motion and four-view original pixels',
            'Sealed original saved processing, pixel and physical review, and pairwise comparison acceptance'],
        'reason': None})
    (ROOT / 'result.json').write_text(json.dumps(current, indent=2) + '\n')


if __name__ == '__main__':
    main()
