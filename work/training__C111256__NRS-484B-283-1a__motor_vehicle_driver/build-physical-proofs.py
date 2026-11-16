"""Run three synthetic completion branches and lifecycle rejection per case."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
SCRIPT = HERE / 'run-physical-mock.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for entry in manifest['cases']:
    case = entry['case_id'].rsplit('__', 1)[1]
    directory = HERE / 'physical-proofs' / case
    directory.mkdir(parents=True, exist_ok=True)
    fixtures = []
    lifecycle = None
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
        output = directory / (kind + '.json')
        log = directory / (kind + '.log')
        command = [str(ROOT / '.venv-cpu/bin/python'), str(SCRIPT), '--case', case,
                   '--kind', kind, '--output', str(output)]
        with log.open('w') as stream:
            completed = subprocess.run(command, cwd=ROOT, stdout=stream,
                                       stderr=subprocess.STDOUT, timeout=30)
        if completed.returncode:
            raise ValueError(f'{case} {kind}: {log.read_text()}')
        if kind == 'lifecycle':
            lifecycle = {'events': json.loads(output.read_text())['events'],
                         'exit_code': 0, 'log': str(log.relative_to(HERE)),
                         'log_sha256': sha(log)}
        else:
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': 0, 'log': str(log.relative_to(HERE)),
                             'log_sha256': sha(log), 'result': str(output.relative_to(HERE)),
                             'result_sha256': sha(output)})
    proof_path = directory / 'proof.json'
    proof_path.write_text(json.dumps({
        'format': 'c111256-synthetic-physical-branch-proof',
        'case_id': entry['case_id'],
        'construction_sha256': entry['construction_sha256'],
        'fixtures_are_cpu_mocks': True,
        'original_native_motion_verified': False,
        'original_pixels_verified': False,
        'fixtures': fixtures, 'lifecycle': lifecycle}, indent=2) + '\n')
    entry['physical_preparation'] = {'receipt': str(proof_path.relative_to(HERE)),
                                     'sha256': sha(proof_path)}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(MANIFEST),
                  'scope': 'synthetic CPU mocks only; no original Native acceptance'}))
