"""Run and bind all exact-case physical-classifier and closure CPU fixtures."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.physical_preparation import validate  # noqa: E402

KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    script = ROOT / 'physical_fixture_proof.py'
    for entry in manifest['cases']:
        case_id = entry['case_id']
        short = case_id.rsplit('__', 1)[-1]
        proof_dir = ROOT / 'physical-proofs' / short
        proof_dir.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in (*KINDS, 'lifecycle'):
            output = proof_dir / (kind + '.json')
            log = proof_dir / (kind + '.log')
            command = [str(REPO / '.venv-cpu/bin/python'), str(script),
                       '--manifest', str(manifest_path), '--case', case_id,
                       '--kind', kind, '--output', str(output)]
            with log.open('w') as stream:
                subprocess.run(command, cwd=REPO, stdout=stream,
                               stderr=subprocess.STDOUT, check=True, timeout=60)
            printable = '.venv-cpu/bin/python work/' + ROOT.name + '/physical_fixture_proof.py'
            printable += ' --manifest work/' + ROOT.name + '/execution-manifest.json'
            printable += ' --case ' + case_id + ' --kind ' + kind
            printable += ' --output work/' + ROOT.name + '/physical-proofs/' + short + '/' + kind + '.json'
            row = {'command': printable, 'exit_code': 0, 'kind': kind,
                   'log': 'physical-proofs/' + short + '/' + kind + '.log',
                   'log_sha256': sha(log),
                   'result': 'physical-proofs/' + short + '/' + kind + '.json',
                   'result_sha256': sha(output)}
            if kind == 'lifecycle':
                row['events'] = EVENTS
                lifecycle = row
            else:
                fixtures.append(row)
        receipt = {'format': 'worker-c125714-physical-preparation',
                   'case_id': case_id, 'construction_sha256': entry['construction_sha256'],
                   'diagnostic_fixture_only': True,
                   'fixture_script': 'physical_fixture_proof.py',
                   'fixture_script_sha256': sha(script),
                   'fixtures': fixtures, 'lifecycle': lifecycle,
                   'physical_acceptance_claimed': False}
        receipt_path = proof_dir / 'receipt.json'
        write(receipt_path, receipt)
        entry['physical_preparation'] = {
            'receipt': 'physical-proofs/' + short + '/receipt.json',
            'sha256': sha(receipt_path)}
        validate(REPO, ROOT, entry)
        print(case_id + ': three physical outcomes and closure passed pinned validator')
    write(manifest_path, manifest)
    print('selected_cases=' + str(len(manifest['cases'])))


if __name__ == '__main__':
    main()
