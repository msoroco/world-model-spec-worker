"""Reprove C229398 candidates against the delivery-bound selected manifest."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
EXPECTED_MANIFEST_SHA = 'a001d0fa706890c62124235a1a65e5a8d79e7139dc739ca818495e320e30bb3d'
DECODER = REPO / '.runtime-work/decoder-update16/.lake/build/bin/adapterCheck'
LIBRARY = REPO / 'runtime/pipeline/library'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run_stage(args, log):
    with log.open('w') as output:
        result = subprocess.run(
            args, cwd=REPO, stdout=output, stderr=subprocess.STDOUT,
            check=False,
            env={**os.environ,
                 'SCENARIO_PIPELINE_OUTPUT_ROOT': str(REPO / '.runtime-work/c229398-rebound-chain-output'),
                 'PYTHONDONTWRITEBYTECODE': '1'},
        )
    require(result.returncode == 0,
            'Pinned stage failed (exit ' + str(result.returncode) + '): ' + str(log))
    receipt = json.loads(log.read_text())
    require(receipt.get('simulation_started') is False or
            receipt.get('recorded_only') is True or receipt.get('passed') is True,
            'Stage receipt did not report a passing CPU path: ' + str(log))
    require(sha(MANIFEST) == EXPECTED_MANIFEST_SHA, 'Selected manifest changed during proof')
    return receipt


def prove(group, candidate):
    case = HERE.name + '__' + group
    prefix = 'rebound-chain-' + group + '-' + candidate
    output_prefix = REPO / '.runtime-work' / ('c229398-' + prefix)
    offline = Path(str(output_prefix) + '-offline')
    compatibility = Path(str(output_prefix) + '-compatibility')
    saved = Path(str(output_prefix) + '-saved')
    for path in (offline, compatibility, saved):
        require(not path.exists(), 'Refusing to overwrite previous attempt: ' + str(path))
    base = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py')]
    common = ['--manifest', str(MANIFEST), '--case', case]
    offline_log = HERE / (prefix + '-offline.log')
    run_stage(base + ['offline'] + common + ['--candidate', candidate,
                                             '--output', str(offline)], offline_log)
    selection = HERE / (prefix + '-offline-selection.json')
    shutil.copyfile(offline / 'candidate-selection.json', selection)
    compat_log = HERE / (prefix + '-compatibility.log')
    run_stage(base + ['compatibility'] + common + ['--candidate', candidate,
                                                   '--output', str(compatibility),
                                                   '--library', str(LIBRARY),
                                                   '--validator', str(DECODER)], compat_log)
    positive = HERE / (prefix + '-analysis.log')
    negative = HERE / (prefix + '-negative-analysis.log')
    shutil.copyfile(compatibility / 'compatibility-analysis.log', positive)
    shutil.copyfile(compatibility / 'negative-analysis.log', negative)
    saved_log = HERE / (prefix + '-saved.log')
    run_stage(base + ['process-saved'] + common + ['--attempt', str(compatibility),
                                                   '--output', str(saved),
                                                   '--library', str(LIBRARY),
                                                   '--validator', str(DECODER)], saved_log)
    files = [offline_log, selection, compat_log, positive, negative, saved_log]
    proof = {
        'case_id': case, 'candidate': candidate,
        'selected_manifest_sha256': EXPECTED_MANIFEST_SHA,
        'cpu_chain_passed': True, 'recorded_only': True,
        'original_native_observed': False, 'delivery_ready': False,
        'receipts': {file.name: sha(file) for file in files},
    }
    (HERE / (prefix + '-proof.json')).write_text(json.dumps(proof, indent=2) + '\n')
    return group + '/' + candidate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('groups', nargs='+')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    require(sha(MANIFEST) == EXPECTED_MANIFEST_SHA, 'Selected manifest hash mismatch')
    manifest = json.loads(MANIFEST.read_text())
    allowed = {entry['case_id'].rsplit('__', 1)[-1] for entry in manifest['cases']}
    require(set(args.groups) <= allowed and len(args.groups) == len(set(args.groups)),
            'Unknown or duplicate delivery-bound case group')
    require(1 <= args.jobs <= 4 and DECODER.is_file(),
            'Invalid concurrency or missing pinned decoder')
    work = [(group, candidate) for group in args.groups for candidate in CANDIDATES]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(prove, *item): item for item in work}
        for future in concurrent.futures.as_completed(futures):
            print(future.result(), 'passed', flush=True)


if __name__ == '__main__':
    main()
