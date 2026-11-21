"""Run all draft newly laid capture candidates through pinned offline checks."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-newly-laid-finalized-manifest.json'
CASES = ('newly_laid_crossing', 'newly_laid_avoidance')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    manifest = json.loads(MANIFEST.read_text())
    if [row['case_id'] for row in manifest['cases']] != [HERE.name + '__' + name for name in CASES]:
        raise ValueError('Draft newly laid cases changed')
    rows = []
    for case in CASES:
        for candidate in CANDIDATES:
            label = case + '-' + candidate
            output = ROOT / '.runtime-work' / ('c183370-update137-' + label)
            log = HERE / ('update137-' + label + '-offline.log')
            if output.exists() or log.exists():
                raise ValueError('Preserve earlier newly laid offline run: ' + label)
            command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', HERE.name + '__' + case,
                       '--candidate', candidate, '--output', str(output),
                       '--python', sys.executable]
            with log.open('x') as stream:
                subprocess.run(command, cwd=ROOT, stdout=stream,
                               stderr=subprocess.STDOUT, check=True)
            receipt = json.loads((output / 'candidate-selection.json').read_text())
            if receipt['manifest_sha256'] != sha(MANIFEST) or receipt['candidate_id'] != candidate:
                raise ValueError('Newly laid offline selection differs')
            rows.append({'case_id': HERE.name + '__' + case,
                         'candidate_id': candidate,
                         'construction_sha256': receipt['construction_sha256'],
                         'selection_sha256': sha(output / 'candidate-selection.json'),
                         'log': log.name, 'log_sha256': sha(log),
                         'offline_passed': True})
    result = {'format': 'c183370-newly-laid-finalized-offline-matrix-v1',
              'manifest_sha256': sha(MANIFEST), 'candidates': rows,
              'passed': len(rows), 'source_finalization_proven': False,
              'original_native_observed': False,
              'physical_or_legal_acceptance_claimed': False}
    path = HERE / 'update137-newly-laid-finalized-offline-matrix.json'
    if path.exists():
        raise ValueError('Preserve earlier newly laid matrix')
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': len(rows), 'manifest_sha256': sha(MANIFEST),
                      'matrix_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    prove()
