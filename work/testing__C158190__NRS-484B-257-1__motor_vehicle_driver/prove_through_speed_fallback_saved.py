"""Replay each exact speed fallback through recorded-only saved processing."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'through-speed-compatibility-manifest.json'
VALIDATOR = '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove(entry, candidate):
    speed = int(entry['case_id'].rsplit('_', 1)[1])
    ident = candidate['id']
    attempt = REPO / f'.runtime-work/c158190-speed-{speed}-{ident}-compat-v1'
    output = REPO / f'.runtime-work/c158190-speed-{speed}-{ident}-saved-v1'
    cmd = [sys.executable, 'runtime.py', 'process-saved', '--manifest',
           str(MANIFEST.relative_to(REPO)), '--case', entry['case_id'],
           '--attempt', str(attempt.relative_to(REPO)), '--output',
           str(output.relative_to(REPO)), '--library', 'runtime/library',
           '--validator', VALIDATOR]
    run = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True)
    if run.returncode:
        raise ValueError(f'{entry["case_id"]} {ident}: {run.stdout}\n{run.stderr}')
    receipt_path = output / 'v0001/processing.json'
    receipt = json.loads(receipt_path.read_text())
    if (receipt['passed'] is not True or receipt['case_id'] != entry['case_id']
            or receipt['candidate_id'] != ident
            or receipt['recorded_only'] is not True
            or receipt['originals_preserved'] is not True
            or receipt['physical_acceptance_claimed'] is not False
            or receipt['legal_acceptance_claimed'] is not False):
        raise ValueError('Fallback saved receipt lacks recorded-only proof')
    return {'case_id': entry['case_id'], 'candidate_id': ident,
            'compatibility_receipt_sha256': sha(attempt / 'compatibility.json'),
            'saved_processing_sha256': sha(receipt_path)}


def main():
    manifest = json.loads(MANIFEST.read_text())
    work = [(entry, candidate) for entry in manifest['cases']
            for candidate in entry['candidates']]
    if len(work) != 9:
        raise ValueError('Expected nine exact speed fallbacks')
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(prove, entry, candidate) for entry, candidate in work]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: (item['case_id'], item['candidate_id']))
    report = {'format': 'c158190-through-speed-fallback-saved-proof',
              'candidates': results, 'all_passed': True,
              'recorded_only': True, 'native_feasibility_proven': False}
    (ROOT / 'through-speed-fallback-saved-proof.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'saved_fallbacks': len(results)}))


if __name__ == '__main__':
    main()
