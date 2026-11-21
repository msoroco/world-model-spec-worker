"""Run source-shaped physical and lifecycle CPU checks for the newly laid pair."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'draft-newly-laid-finalized-manifest.json'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        short = case.removeprefix(HERE.name + '__')
        directory = HERE / 'selected-physical-preparation' / short
        directory.mkdir(parents=True, exist_ok=True)
        fixtures = []
        lifecycle = None
        for kind in KINDS:
            result = directory / (kind + '.json')
            log = directory / (kind + '.log')
            command = [sys.executable, str(HERE / 'run_physical_fixture.py'),
                       '--manifest', str(MANIFEST), '--case', case,
                       '--kind', kind, '--output', str(result)]
            if result.exists():
                result.unlink()
            run = subprocess.run(command, cwd=REPO, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.write_text(run.stdout)
            if run.returncode:
                raise RuntimeError(f'{case} {kind}: {run.stdout}')
            relative = lambda path: str(path.relative_to(HERE))
            record = {'command': ' '.join(command), 'exit_code': run.returncode,
                      'log': relative(log), 'log_sha256': digest(log),
                      'result': relative(result), 'result_sha256': digest(result)}
            if kind == 'lifecycle':
                lifecycle = dict(record, events=EVENTS)
            else:
                fixtures.append(dict(record, kind=kind))
        proof = {'format': 'c183370-selected-physical-cpu-fixtures-v1',
                 'case_id': case, 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures, 'lifecycle': lifecycle,
                 'fixtures_are_cpu_mocks': True,
                 'original_native_motion_verified': False}
        path = directory / 'proof.json'
        path.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
        print(json.dumps({'case': case, 'proof': str(path.relative_to(HERE)),
                          'sha256': digest(path)}))


if __name__ == '__main__':
    main()
