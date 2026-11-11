"""Reprove every exact construction against the delivery execution manifest."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
LIBRARY = REPO / 'runtime/library'
VALIDATOR = REPO / '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(args, log):
    process = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    log.write_text(process.stdout + process.stderr)
    if process.returncode:
        raise ValueError(f'Exact execution reproof failed ({process.returncode}): {log}')


def main():
    manifest = json.loads(MANIFEST.read_text())
    records = []
    for case in manifest['cases']:
        suffix = case['case_id'].split('__')[-1]
        candidates = [('primary', None)] + [(item['id'], item) for item in case['candidates']]
        candidate_proofs = []
        for candidate_id, candidate in candidates:
            tag = suffix + '-' + candidate_id
            out_offline = REPO / '.runtime-work' / f'c10364-{tag}-execution-offline-proof-v2'
            off_log = ROOT / 'cases' / f'execution-offline-{tag}.log'
            args = [sys.executable, str(REPO / 'runtime.py'), 'offline',
                    '--manifest', str(MANIFEST), '--case', case['case_id'],
                    '--output', str(out_offline), '--python', sys.executable]
            if candidate_id != 'primary':
                args.extend(['--candidate', candidate_id])
            run(args, off_log)
            out_compat = REPO / '.runtime-work' / f'c10364-{tag}-execution-compat-proof-v2'
            compat_log = ROOT / 'cases' / f'execution-compat-{tag}.log'
            args = [sys.executable, str(REPO / 'runtime.py'), 'compatibility',
                    '--manifest', str(MANIFEST), '--case', case['case_id'],
                    '--output', str(out_compat), '--library', str(LIBRARY),
                    '--validator', str(VALIDATOR)]
            if candidate_id != 'primary':
                args.extend(['--candidate', candidate_id])
            run(args, compat_log)
            receipt = json.loads((out_compat / 'compatibility.json').read_text())
            if (receipt.get('case_id') != case['case_id'] or
                    receipt.get('candidate_id') != candidate_id or not receipt.get('passed') or
                    receipt.get('construction_sha256') !=
                    (case if candidate is None else candidate)['construction_sha256']):
                raise ValueError('Exact execution compatibility identity/hash differs: ' + tag)
            receipt_path = ROOT / 'cases' / f'execution-receipt-{tag}.json'
            shutil.copyfile(out_compat / 'compatibility.json', receipt_path)
            candidate_proofs.append({'candidate_id': candidate_id,
                'offline_log': str(off_log.relative_to(ROOT)), 'offline_log_sha256': digest(off_log),
                'compatibility_log': str(compat_log.relative_to(ROOT)),
                'compatibility_log_sha256': digest(compat_log),
                'compatibility_receipt': str(receipt_path.relative_to(ROOT)),
                'compatibility_receipt_sha256': digest(receipt_path),
                'construction_sha256': receipt['construction_sha256']})
            print('offline+compat ' + tag, flush=True)
        records.append({'case_id': case['case_id'], 'candidates': candidate_proofs})
    output = {'format': 'worker-alley-execution-reproof',
              'assignment_id': manifest['assignment_id'],
              'execution_manifest_sha256': digest(MANIFEST),
              'cases': records, 'physical_acceptance_claimed': False,
              'legal_acceptance_claimed': False}
    (ROOT / 'execution-reproof.json').write_text(json.dumps(output, indent=2) + '\n')
    print('All nine execution cases and 27 alternatives pass exact offline/compatibility', flush=True)


if __name__ == '__main__':
    main()
