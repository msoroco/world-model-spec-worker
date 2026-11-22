"""Run exact cutover offline selection for every retained selected candidate."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'current-runtime-probe-manifest.json'
OUTPUT = HERE / 'current-runtime-offline-index.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for case in manifest['cases']:
        for selected in [case, *case['candidates']]:
            cid = case['case_id']
            candidate = selected.get('id', 'primary')
            out = ROOT / '.runtime-work/c183370-cutover-probe/offline-matrix' / cid / candidate
            command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', cid,
                       '--candidate', candidate, '--output', str(out),
                       '--python', sys.executable]
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            if run.returncode:
                raise RuntimeError(f'{cid}/{candidate}: {run.stderr[-1500:]}')
            receipt = json.loads(run.stdout)
            if not receipt['offline_passed'] or receipt['simulation_started']:
                raise ValueError(f'Offline selection incomplete: {cid}/{candidate}')
            selection = out / 'candidate-selection.json'
            selection_json = json.loads(selection.read_text())
            if selection_json['manifest_sha256'] != sha(MANIFEST):
                raise ValueError(f'Manifest binding mismatch: {cid}/{candidate}')
            rows.append({'case_id': cid, 'candidate_id': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'selection_sha256': sha(selection)})
    OUTPUT.write_text(json.dumps({'format': 'current-runtime-offline-matrix',
                                  'manifest_sha256': sha(MANIFEST),
                                  'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
                                  'count': len(rows), 'rows': rows}, indent=2,
                                 sort_keys=True) + '\n')
    print(json.dumps({'count': len(rows), 'index_sha256': sha(OUTPUT)}))


if __name__ == '__main__':
    main()
