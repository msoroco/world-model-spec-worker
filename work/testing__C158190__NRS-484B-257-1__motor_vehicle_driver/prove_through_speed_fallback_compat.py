"""Run pinned positive and negative compatibility for nine exact fallbacks."""

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
    ident = candidate['id']
    speed = int(entry['case_id'].rsplit('_', 1)[1])
    output = REPO / f'.runtime-work/c158190-speed-{speed}-{ident}-compat-v1'
    cmd = [sys.executable, 'runtime.py', 'compatibility', '--manifest',
           str(MANIFEST.relative_to(REPO)), '--case', entry['case_id'],
           '--candidate', ident, '--output', str(output.relative_to(REPO)),
           '--library', 'runtime/library', '--validator', VALIDATOR]
    if not (output / 'compatibility.json').is_file():
        run = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True)
        if run.returncode:
            raise ValueError(f'{entry["case_id"]} {ident}: {run.stdout}\n{run.stderr}')
    receipt = json.loads((output / 'compatibility.json').read_text())
    if (receipt['passed'] is not True or receipt['case_id'] != entry['case_id']
            or receipt['candidate_id'] != ident
            or receipt['construction_sha256'] != candidate['construction_sha256']
            or receipt.get('negative_removed') != 'visibility_rays.jsonl'):
        raise ValueError('Fallback compatibility receipt differs from exact candidate')
    return {'case_id': entry['case_id'], 'candidate_id': ident,
            'construction_sha256': candidate['construction_sha256'],
            'compatibility_receipt_sha256': sha(output / 'compatibility.json'),
            'negative_removed': receipt['negative_removed']}


def main():
    manifest = json.loads(MANIFEST.read_text())
    work = [(entry, candidate) for entry in manifest['cases']
            for candidate in entry['candidates']]
    if len(work) != 9:
        raise ValueError('Expected nine exact fallback candidates')
    receipts = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(prove, entry, candidate) for entry, candidate in work]
        for future in as_completed(futures):
            receipts.append(future.result())
    receipts.sort(key=lambda item: (item['case_id'], item['candidate_id']))
    report = {'format': 'c158190-through-speed-fallback-compatibility-proof',
              'candidates': receipts, 'all_passed': True,
              'source_kind': 'synthetic compatibility diagnostics',
              'native_feasibility_proven': False}
    (ROOT / 'through-speed-fallback-compat-proof.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'fallbacks': len(receipts)}))


if __name__ == '__main__':
    main()
