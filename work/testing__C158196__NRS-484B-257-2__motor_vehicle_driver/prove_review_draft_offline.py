"""Run pinned-runtime offline checks on staged review-context bundles."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'review-draft-manifest.json'
OUTPUT = REPO / '.runtime-work/c158196-review-offline-all-r2'
LOGS = ROOT / 'review-draft/draft-offline-proofs'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    LOGS.mkdir(parents=True, exist_ok=True)
    receipts = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for candidate in [{'id': 'primary', **entry}, *entry['candidates']]:
            ident = candidate['id']
            destination = OUTPUT / (suffix + '-' + ident)
            log_path = LOGS / (suffix + '-' + ident + '.log')
            command = [sys.executable, str(REPO / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--output', str(destination), '--python', sys.executable]
            if ident != 'primary':
                command += ['--candidate', ident]
            with log_path.open('w') as stream:
                run = subprocess.run(command, cwd=REPO, stdout=stream,
                                     stderr=subprocess.STDOUT, check=False)
            receipt = {'case_id': entry['case_id'], 'candidate_id': ident,
                       'construction': candidate['construction'],
                       'construction_sha256': candidate['construction_sha256'],
                       'command': command, 'exit_code': run.returncode,
                       'log': str(log_path.relative_to(ROOT)),
                       'log_sha256': sha(log_path)}
            receipts.append(receipt)
            print(suffix, ident, run.returncode, flush=True)
            if run.returncode:
                break
    index = {'format': 'c158196-review-draft-offline-proofs',
             'manifest_sha256': sha(MANIFEST), 'receipts': receipts}
    (ROOT / 'review-draft/draft-offline-proof-index.json').write_text(
        json.dumps(index, indent=2) + '\n')
    if len(receipts) != 24 or any(row['exit_code'] for row in receipts):
        raise SystemExit('Staged offline proof incomplete')


if __name__ == '__main__':
    main()
