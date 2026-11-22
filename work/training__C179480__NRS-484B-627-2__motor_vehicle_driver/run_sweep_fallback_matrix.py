"""Run exact draft sweep fallback CPU proofs under the current runtime."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = ROOT / '.runtime-work/c179480-native-sweep'
MANIFEST = HERE / 'sweep-candidate-manifest.json'
TAG = 'sweep-qualified'
LIBRARY = ROOT / 'runtime/pipeline/library'
VALIDATOR = ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proof(case_id, candidate, compatibility_only=False):
    name = f'{case_id}-{candidate}'
    attempt = ASSETS / ('compatibility-' + TAG) / case_id / candidate
    saved = ASSETS / ('saved-' + TAG) / case_id / candidate
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ASSETS / ('adapter-' + TAG) / case_id / candidate)
    env['MPLCONFIGDIR'] = str(ASSETS / 'mpl')
    args = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py')]
    common = ['--manifest', str(MANIFEST), '--case', case_id,
              '--library', str(LIBRARY), '--validator', str(VALIDATOR)]
    compat_log = HERE / f'{TAG}-{name}-compatibility.log'
    if not compat_log.is_file():
        call = args + ['compatibility', *common, '--candidate', candidate,
                       '--output', str(attempt)]
        completed = subprocess.run(call, cwd=ROOT, env=env, capture_output=True, text=True)
        compat_log.write_text(completed.stdout + completed.stderr)
        if completed.returncode:
            raise RuntimeError(f'{name} compatibility exit {completed.returncode}: '
                               + (completed.stdout + completed.stderr)[-900:])
    compat = json.loads(compat_log.read_text())
    entry = next(item for item in json.loads(MANIFEST.read_text())['cases']
                 if item['case_id'] == case_id)
    selected = (entry if candidate == 'primary' else
                next(item for item in entry['candidates'] if item['id'] == candidate))
    if (not compat['passed'] or compat['case_id'] != case_id or
            compat['candidate_id'] != candidate or
            compat['construction_sha256'] != selected['construction_sha256'] or
            compat['runtime_manifest_sha256'] !=
            json.loads(MANIFEST.read_text())['runtime_manifest_sha256']):
        raise ValueError(f'{name} compatibility receipt mismatch')
    if compatibility_only:
        return {'case_id': case_id, 'candidate_id': candidate,
                'compatibility_log_sha256': sha(compat_log)}
    saved_log = HERE / f'{TAG}-{name}-saved.log'
    if not saved_log.is_file():
        call = args + ['process-saved', *common, '--attempt', str(attempt),
                       '--output', str(saved)]
        completed = subprocess.run(call, cwd=ROOT, env=env, capture_output=True, text=True)
        saved_log.write_text(completed.stdout + completed.stderr)
        if completed.returncode:
            raise RuntimeError(f'{name} saved exit {completed.returncode}: '
                               + (completed.stdout + completed.stderr)[-900:])
    saved_result = json.loads(saved_log.read_text())
    if (not saved_result['passed'] or saved_result['case_id'] != case_id or
            not saved_result['recorded_only'] or
            not saved_result['originals_preserved'] or
            saved_result['missing_evidence']):
        raise ValueError(f'{name} saved receipt incomplete')
    return {'case_id': case_id, 'candidate_id': candidate,
            'compatibility_log_sha256': sha(compat_log),
            'saved_log_sha256': sha(saved_log)}


def main():
    global MANIFEST, TAG
    parser = argparse.ArgumentParser()
    parser.add_argument('--compatibility-only', action='store_true')
    parser.add_argument('--skip-first', action='store_true')
    parser.add_argument('--include-primary', action='store_true')
    parser.add_argument('--base', action='store_true',
                        help='Use the current four base-case candidate manifest')
    parser.add_argument('--only-ready', action='store_true',
                        help='Process only candidates with completed compatibility logs')
    parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if args.base:
        MANIFEST = HERE / 'candidate-matrix-manifest.json'
        TAG = 'base-current'
    manifest = json.loads(MANIFEST.read_text())
    tasks = [(entry['case_id'], candidate)
             for entry in manifest['cases']
             for candidate in ((['primary'] if args.include_primary else []) +
                               [item['id'] for item in entry['candidates']])]
    if args.skip_first:
        tasks = tasks[1:]
    if args.only_ready:
        tasks = [(case_id, candidate) for case_id, candidate in tasks
                 if (HERE / f'{TAG}-{case_id}-{candidate}-compatibility.log').is_file()]
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(proof, case_id, candidate, args.compatibility_only):
                   (case_id, candidate) for case_id, candidate in tasks}
        for future in concurrent.futures.as_completed(futures):
            case_id, candidate = futures[future]
            try:
                row = future.result()
            except Exception as exc:
                print(f'FAIL {case_id} {candidate}: {exc}', flush=True)
                raise
            print(f'PASS {case_id} {candidate}', flush=True)
            rows.append(row)
    result = {'format': 'c179480-draft-sweep-fallback-matrix-v1',
              'candidate_manifest_sha256': sha(MANIFEST),
              'compatibility_only': args.compatibility_only,
              'count': len(rows), 'rows': sorted(rows, key=lambda row:
                                                  (row['case_id'], row['candidate_id'])),
              'passed': True, 'selected_cases': 0,
              'physical_or_legal_acceptance_claimed': False}
    target = HERE / (f'{TAG}-compatibility-index.json' if args.compatibility_only
                     else f'{TAG}-complete-index.json')
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(f'INDEX {target} {sha(target)}', flush=True)


if __name__ == '__main__':
    main()
