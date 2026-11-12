"""Run pinned exact offline materialization for all speed-sweep fallbacks."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'through-speed-compatibility-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    receipts = []
    for entry in manifest['cases']:
        speed = int(entry['case_id'].rsplit('_', 1)[1])
        for candidate in entry['candidates']:
            ident = candidate['id']
            path = ROOT / candidate['construction']
            assert sha(path) == candidate['construction_sha256']
            output = REPO / f'.runtime-work/c158190-speed-{speed}-{ident}-offline-v1'
            cmd = [sys.executable, 'runtime.py', 'offline', '--manifest',
                   str(MANIFEST.relative_to(REPO)), '--case', entry['case_id'],
                   '--candidate', ident, '--output', str(output.relative_to(REPO))]
            run = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True)
            if run.returncode:
                raise ValueError(f'{entry["case_id"]} {ident}: {run.stdout}\n{run.stderr}')
            log = output / 'offline.log'
            source = log.read_text()
            if 'Ran 34 tests' not in source or 'OK' not in source:
                raise ValueError('Materialized fallback CPU tests failed')
            receipts.append({'case_id': entry['case_id'], 'candidate_id': ident,
                             'construction_sha256': candidate['construction_sha256'],
                             'offline_log_sha256': sha(log), 'materialized_test_count': 34})
    report = {'format': 'c158190-through-speed-fallback-offline-proof',
              'cases': receipts, 'all_passed': len(receipts) == 9,
              'native_feasibility_proven': False}
    (ROOT / 'through-speed-fallback-offline-proof.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'fallbacks': len(receipts)}))


if __name__ == '__main__':
    main()
