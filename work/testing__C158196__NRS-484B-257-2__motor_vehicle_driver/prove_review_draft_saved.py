"""Run official recorded-only processing on staged primary diagnostic attempts."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'review-draft-manifest.json'
VALIDATOR = REPO / '.runtime-work/c158196-current-decoder/.lake/build/bin/adapterCheck'
ATTEMPTS = REPO / '.runtime-work/c158196-review-compat-all'
OUTPUT = REPO / '.runtime-work/c158196-review-saved-all'
LOGS = ROOT / 'review-draft/draft-saved-proofs'
INDEX = LOGS / 'index.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        attempt = ATTEMPTS / (suffix + '-primary')
        log = LOGS / (suffix + '.log')
        command = [sys.executable, str(REPO / 'runtime.py'), 'process-saved',
                   '--manifest', str(MANIFEST), '--case', case,
                   '--attempt', str(attempt), '--output', str(OUTPUT / suffix),
                   '--library', str(REPO / 'runtime/library'),
                   '--validator', str(VALIDATOR)]
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        with log.open('w') as stream:
            run = subprocess.run(command, cwd=REPO, env=env, stdout=stream,
                                 stderr=subprocess.STDOUT, timeout=600, check=False)
        row = {'case_id': case, 'construction_sha256': entry['construction_sha256'],
               'command': command, 'exit_code': run.returncode,
               'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log)}
        rows.append(row)
        INDEX.write_text(json.dumps({'format': 'c158196-review-draft-saved-proofs',
                                     'manifest_sha256': sha(MANIFEST),
                                     'receipts': rows}, indent=2) + '\n')
        if run.returncode:
            raise SystemExit('Staged saved processing failed for ' + case)
        receipt = json.loads(log.read_text())
        if receipt.get('passed') is not True or receipt.get('recorded_only') is not True:
            raise SystemExit('Staged saved processing receipt did not pass for ' + case)
        print(suffix, 'passed', flush=True)
    if len(rows) != len(manifest['cases']):
        raise SystemExit('Staged saved processing incomplete')


if __name__ == '__main__':
    main()
