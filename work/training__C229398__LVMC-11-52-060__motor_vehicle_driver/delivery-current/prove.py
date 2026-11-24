"""Replay the selected synthetic CPU chains against the pinned runtime."""
import concurrent.futures
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'execution-manifest.json'
ROOT = REPO / '.runtime-work/c229398-delivery-current'
LIBRARY = REPO / 'runtime/library'
DECODER = REPO / '.runtime-work/c229398-pinned-decoder/.lake/build/bin/adapterCheck'
GROUPS = ('below_15_ft', 'at_15_ft', 'above_15_ft')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(args, log):
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
           'SCENARIO_PIPELINE_OUTPUT_ROOT': str(ROOT),
           'TMPDIR': str(ROOT / 'tmp'), 'MPLCONFIGDIR': str(ROOT / 'mpl')}
    with log.open('w') as stream:
        result = subprocess.run(args, cwd=REPO, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise ValueError(f'{log} failed exit {result.returncode}: {log.read_text()[-1500:]}')
    return json.loads(log.read_text())


def prove(group, candidate):
    prefix = f'{group}-{candidate}'
    case = f'{PACKAGE.name}__{group}'
    common = ['--manifest', str(MANIFEST), '--case', case, '--candidate', candidate]
    base = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py')]
    offline_dir = ROOT / f'{prefix}-offline'
    compat_dir = ROOT / f'{prefix}-compat'
    saved_dir = ROOT / f'{prefix}-saved'
    offline_log = HERE / f'{prefix}-offline.json'
    compat_log = HERE / f'{prefix}-compatibility.json'
    saved_log = HERE / f'{prefix}-saved.json'
    offline = (json.loads(offline_log.read_text()) if offline_dir.exists() and offline_log.is_file()
               else stage(base + ['offline'] + common + ['--output', str(offline_dir)], offline_log))
    if offline.get('offline_passed') is not True or offline.get('simulation_started') is not False:
        raise ValueError(f'Offline receipt failed: {prefix}')
    shutil.copyfile(offline_dir / 'candidate-selection.json', HERE / f'{prefix}-selection.json')
    compat = (json.loads(compat_log.read_text()) if compat_dir.exists() and compat_log.is_file()
              else stage(base + ['compatibility'] + common + ['--output', str(compat_dir),
                         '--library', str(LIBRARY), '--validator', str(DECODER)], compat_log))
    if compat.get('passed') is not True or compat.get('runtime_manifest_sha256') != sha(REPO / 'runtime/SOURCE-MANIFEST.json'):
        raise ValueError(f'Compatibility receipt failed: {prefix}')
    shutil.copyfile(compat_dir / 'compatibility-analysis.log', HERE / f'{prefix}-analysis.log')
    shutil.copyfile(compat_dir / 'negative-analysis.log', HERE / f'{prefix}-negative.log')
    saved = stage(base + ['process-saved', '--manifest', str(MANIFEST), '--case', case,
                  '--attempt', str(compat_dir),
                  '--output', str(saved_dir), '--library', str(LIBRARY),
                  '--validator', str(DECODER)], saved_log)
    if saved.get('passed') is not True or saved.get('recorded_only') is not True or saved.get('originals_preserved') is not True:
        raise ValueError(f'Saved receipt failed: {prefix}')
    files = [offline_log, HERE / f'{prefix}-selection.json', compat_log,
             HERE / f'{prefix}-analysis.log', HERE / f'{prefix}-negative.log', saved_log]
    proof = {'case_id': case, 'candidate_id': candidate, 'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
             'selected_manifest_sha256_at_run': sha(MANIFEST), 'passed': True,
             'diagnostic_only': True, 'original_native_observed': False,
             'physical_acceptance_claimed': False,
             'receipts': {p.name: sha(p) for p in files}}
    (HERE / f'{prefix}-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    return prefix


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', action='append', choices=CANDIDATES)
    parser.add_argument('--group', action='append', choices=GROUPS)
    args = parser.parse_args()
    (ROOT / 'tmp').mkdir(parents=True, exist_ok=True)
    (ROOT / 'mpl').mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(prove, group, candidate)
                   for group in (args.group or GROUPS)
                   for candidate in (args.candidate or CANDIDATES)]
        for future in concurrent.futures.as_completed(futures):
            print(future.result(), flush=True)
