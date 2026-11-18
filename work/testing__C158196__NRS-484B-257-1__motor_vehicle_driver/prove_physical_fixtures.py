"""Record source-bound CPU classifier and lifecycle diagnostic fixtures."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
PREFIX = HERE.relative_to(REPO)
SAVED = {
    'signal_controls_ego': 'primary-process-saved.json',
    'signal_off': 'signal-off-process-saved.json',
    'signal_visible_not_governing': 'signal-visible-process-saved.json',
    'yield_without_signal_control': 'yield-process-saved.json',
}
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        folder = HERE / 'physical-proofs' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        source = Path('.runtime-work/c158196-remaining-channels-sweep') / (suffix + '-primary-compatibility')
        saved = HERE / SAVED[suffix]
        receipt = {'format': 'worker-physical-preparation-fixtures', 'case_id': case,
                   'construction_sha256': entry['construction_sha256'],
                   'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
                   'saved_processing_sha256': sha(saved), 'fixtures': []}
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
            output = folder / (kind + '.json')
            log = folder / (kind + '.log')
            command = ['.venv-cpu/bin/python', str(PREFIX / 'physical_fixture_proof.py'),
                       '--manifest', str(PREFIX / 'execution-manifest.json'),
                       '--case', case, '--source', str(source), '--kind', kind,
                       '--output', str(output.relative_to(REPO)),
                       '--saved-receipt', str(saved.relative_to(REPO))]
            result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
            log.write_text(result.stdout + result.stderr)
            if result.returncode:
                raise RuntimeError(f'{suffix}/{kind} failed: {log.read_text()}')
            item = {'kind': kind, 'command': ' '.join(command), 'exit_code': result.returncode,
                    'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                    'result': str(output.relative_to(HERE)), 'result_sha256': sha(output)}
            if kind == 'lifecycle':
                item['events'] = json.loads(output.read_text())['events']
                if item['events'] != EVENTS:
                    raise ValueError('Lifecycle event order differs')
                receipt['lifecycle'] = item
            else:
                receipt['fixtures'].append(item)
        receipt_path = folder / 'receipt.json'
        write(receipt_path, receipt)
        entry['physical_preparation'] = {'receipt': str(receipt_path.relative_to(HERE)),
                                         'sha256': sha(receipt_path)}
        print(f'{suffix}: met / not_met / unverified and lifecycle passed')
    write(MANIFEST, manifest)


if __name__ == '__main__':
    main()
