"""Run pinned offline preflight on all eight exact unselected bundles."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
AID = HERE.parent.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    manifest = HERE / 'package-manifest.json'
    data = json.loads(manifest.read_text())
    rows = []
    for case in ('reference', 'contrast'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            destination = HERE / 'cpu-proofs' / case / candidate
            if destination.exists():
                # A repeat proof must use a fresh exact materialization.
                raise FileExistsError(destination)
            command = [sys.executable, str(REPO / 'runtime.py'), 'offline',
                       '--manifest', str(manifest), '--case', AID + '__' + case,
                       '--candidate', candidate, '--output', str(destination), '--python', sys.executable]
            completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
            if completed.returncode:
                raise RuntimeError(f'{case}/{candidate}: {completed.stderr[-2000:]} {completed.stdout[-2000:]}')
            selection = json.loads((destination / 'candidate-selection.json').read_text())
            rows.append({'case': case, 'candidate': candidate, 'command': command,
                         'exit_code': completed.returncode,
                         'construction_sha256': selection['construction_sha256'],
                         'offline_log_sha256': sha(destination / 'offline.log'),
                         'materialized_config_sha256': sha(destination / 'config.json'),
                         'request_sha256': sha(destination / 'native-requests.jsonl'),
                         'materialized_selection_sha256': sha(destination / 'candidate-selection.json'),
                         'simulation_started': False, 'selected': False})
    receipt = {'format': 'c111331-exact-offline-draft-proof-v1',
               'manifest_sha256': sha(manifest), 'runtime_manifest_sha256': data['runtime_manifest_sha256'],
               'rows': rows, 'physical_success_claimed': False, 'delivery_ready_claimed': False}
    (HERE / 'cpu-proof-summary.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return {'passed': True, 'candidate_bundles': len(rows),
            'summary_sha256': sha(HERE / 'cpu-proof-summary.json')}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
