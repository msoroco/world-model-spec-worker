"""Collect independently executed CPU physical proof for selected scooter cases."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / 'prove-selected-physical.py'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(path.relative_to(HERE))


def clean_log(s):
    return s.rstrip() + '\n'


def main():
    manifest = json.loads((HERE / 'public-draft-manifest.json').read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        folder = HERE / 'physical-proof' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in KINDS:
            result = folder / (kind + '.json')
            command = [sys.executable, str(SCRIPT), '--case', suffix, '--kind', kind,
                       '--output', str(result)]
            proc = subprocess.run(command, capture_output=True, text=True)
            log = folder / (kind + '.log')
            log.write_text(clean_log(proc.stdout + proc.stderr))
            if proc.returncode:
                raise RuntimeError(log.read_text())
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': proc.returncode, 'log': relative(log),
                             'log_sha256': sha(log), 'result': relative(result),
                             'result_sha256': sha(result)})
        command = [sys.executable, str(SCRIPT), '--case', suffix, '--kind', 'lifecycle']
        proc = subprocess.run(command, capture_output=True, text=True)
        log = folder / 'lifecycle.log'
        log.write_text(clean_log(proc.stdout + proc.stderr))
        if proc.returncode or json.loads(proc.stdout)['events'] != EVENTS:
            raise RuntimeError(log.read_text())
        proof = {'format': 'worker-physical-preparation-v1', 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'], 'fixtures': fixtures,
                 'lifecycle': {'events': EVENTS, 'exit_code': proc.returncode,
                               'log': relative(log), 'log_sha256': sha(log)},
                 'diagnostic_only': True, 'native_execution_claimed': False}
        proof_path = folder / 'proof.json'
        proof_path.write_text(json.dumps(proof, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': relative(proof_path), 'sha256': sha(proof_path)}
    (HERE / 'public-draft-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'physical_proofs': True}))


if __name__ == '__main__':
    main()
