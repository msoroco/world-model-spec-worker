"""Run synthetic original-shaped physical discrimination for ten selected sweep cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from parking_pose import SWEEP_REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c150041-sweep-physical-v2'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    if SCRATCH.exists():
        raise ValueError('fresh physical proof scratch required')
    SCRATCH.mkdir(parents=True)
    manifest = json.loads((ROOT / 'sweep-manifest-draft.json').read_text())
    by_case = {entry['case_id']: entry for entry in manifest['cases']}
    for suffix in SWEEP_REQUESTS:
        folder = ROOT / 'diagnostic' / suffix
        fixtures = []
        for kind in KINDS:
            history = SCRATCH / suffix / kind / 'history.jsonl'
            result = folder / f'physical-{kind}-result.json'
            log = folder / f'physical-{kind}.log'
            command = [sys.executable, str(ROOT / 'physical_proof.py'),
                       '--case', suffix, '--kind', kind, '--history', str(history),
                       '--result', str(result)]
            run = subprocess.run(command, cwd=REPO, env=os.environ, capture_output=True, text=True)
            log.write_text((run.stdout + run.stderr).rstrip() + '\n')
            if run.returncode:
                raise RuntimeError(f'{suffix} {kind} failed: {run.stderr}')
            fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                             'log': log.relative_to(ROOT).as_posix(), 'log_sha256': sha(log),
                             'result': result.relative_to(ROOT).as_posix(),
                             'result_sha256': sha(result)})
        lifecycle = folder / 'physical-lifecycle.log'
        lifecycle.write_text('capture_finished\nencoders_closed\nrestoration_verified\n'
                             'native_exit\nowner_released\nsaved_processing_started\n')
        receipt = {'format': 'worker-physical-preparation',
                   'case_id': ROOT.name + '__' + suffix,
                   'construction_sha256': by_case[ROOT.name + '__' + suffix]['construction_sha256'],
                   'provenance_kind': 'synthetic_fixture', 'physical_acceptance_claimed': False,
                   'fixtures': fixtures,
                   'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                                            'restoration_verified', 'native_exit',
                                            'owner_released', 'saved_processing_started'],
                                 'exit_code': 0, 'log': lifecycle.relative_to(ROOT).as_posix(),
                                 'log_sha256': sha(lifecycle)}}
        path = folder / 'physical-preparation.json'
        path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        by_case[receipt['case_id']]['physical_preparation'] = {
            'receipt': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}
        print(suffix, flush=True)
    (ROOT / 'sweep-manifest-draft.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
