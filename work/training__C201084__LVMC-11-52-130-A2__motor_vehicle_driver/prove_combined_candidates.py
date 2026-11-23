"""Run pinned combined-manifest CPU chains for named draft case groups."""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'current-combined-delivery-draft.json'
DECODER = REPO / '.runtime-work/decoder-update16/.lake/build/bin/adapterCheck'
LIBRARY = REPO / 'runtime/pipeline/library'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run_stage(args, log):
    with log.open('w') as output:
        result = subprocess.run(args, cwd=REPO, stdout=output,
                                stderr=subprocess.STDOUT, check=False,
                                env={**os.environ,
                                     'SCENARIO_PIPELINE_OUTPUT_ROOT': str(
                                         REPO / '.runtime-work/combined-proof-output'),
                                     'PYTHONDONTWRITEBYTECODE': '1'})
    require(result.returncode == 0,
            'Pinned stage failed (exit ' + str(result.returncode) + '): ' + str(log))
    receipt = json.loads(log.read_text())
    require(receipt.get('simulation_started') is False or
            receipt.get('recorded_only') is True or
            receipt.get('passed') is True,
            'Stage receipt did not report a passing CPU path: ' + str(log))
    return receipt


def prove(group, candidate):
    case = HERE.name + '__' + group
    prefix = 'current-combined-' + group + '-' + candidate
    output_prefix = REPO / '.runtime-work' / ('c201084-combined-' + group + '-' + candidate)
    offline = Path(str(output_prefix) + '-offline')
    compatibility = Path(str(output_prefix) + '-compatibility')
    saved = Path(str(output_prefix) + '-saved')
    for path in (offline, compatibility, saved):
        require(not path.exists(), 'Refusing to overwrite previous attempt: ' + str(path))
    base = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py')]
    common = ['--manifest', str(MANIFEST), '--case', case]
    run_stage(base + ['offline'] + common + ['--candidate', candidate,
                                             '--output', str(offline)],
              HERE / (prefix + '-offline.log'))
    shutil.copyfile(offline / 'candidate-selection.json',
                    HERE / (prefix + '-offline-selection.json'))
    run_stage(base + ['compatibility'] + common + ['--candidate', candidate,
                                                   '--output', str(compatibility),
                                                   '--library', str(LIBRARY),
                                                   '--validator', str(DECODER)],
              HERE / (prefix + '-compatibility.log'))
    shutil.copyfile(compatibility / 'negative-analysis.log',
                    HERE / (prefix + '-negative-analysis.log'))
    run_stage(base + ['process-saved'] + common + ['--attempt', str(compatibility),
                                                   '--output', str(saved),
                                                   '--library', str(LIBRARY),
                                                   '--validator', str(DECODER)],
              HERE / (prefix + '-saved.log'))
    return group + '/' + candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('groups', nargs='+')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    allowed = {entry['case_id'].rsplit('__', 1)[-1] for entry in manifest['cases']}
    require(set(args.groups) <= allowed and len(args.groups) == len(set(args.groups)),
            'Unknown or duplicate combined-manifest case group')
    require(1 <= args.jobs <= 4 and DECODER.is_file(),
            'Invalid concurrency or missing pinned decoder')
    work = [(group, candidate) for group in args.groups for candidate in CANDIDATES]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(prove, *item): item for item in work}
        for future in concurrent.futures.as_completed(futures):
            print(future.result(), 'passed', flush=True)


if __name__ == '__main__':
    main()
