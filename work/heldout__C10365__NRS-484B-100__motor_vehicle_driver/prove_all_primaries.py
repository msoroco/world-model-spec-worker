"""Exact offline, compatibility and saved diagnostics for four officer cases."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from worker_exchange.runtime_cli import materialize
from worker_exchange.fixture_recipe import materialize as fixture_materialize
from worker_exchange.saved_processing import copy_sources


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'probe-compatibility-manifest.json'
VALIDATOR = REPO / '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def command(args, log):
    process = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    log.write_text(process.stdout + process.stderr)
    if process.returncode:
        raise ValueError('Exact C10365 proof failed: ' + log.name)
    return json.loads(process.stdout)


def main():
    manifest = json.loads(MANIFEST.read_text())
    (ROOT / 'cases').mkdir(exist_ok=True)
    records = []
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.split('__')[-1]
        offline = REPO / '.runtime-work' / f'c10365-{suffix}-primary-offline-all'
        offline_log = ROOT / 'cases' / f'case-offline-{suffix}-primary.log'
        off = command([sys.executable, str(REPO / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', case_id,
                       '--output', str(offline), '--python', sys.executable], offline_log)
        if not off.get('offline_passed'):
            raise ValueError('Selected offline construction did not pass')
        compatible = REPO / '.runtime-work' / f'c10365-{suffix}-primary-compat-all'
        compatibility_log = ROOT / 'cases' / f'case-compat-{suffix}-primary.log'
        receipt = command([sys.executable, str(REPO / 'runtime.py'), 'compatibility',
                           '--manifest', str(MANIFEST), '--case', case_id,
                           '--output', str(compatible), '--library', str(REPO / 'runtime/library'),
                           '--validator', str(VALIDATOR)], compatibility_log)
        if (not receipt.get('passed') or receipt.get('case_id') != case_id
                or receipt.get('construction_sha256') != entry['construction_sha256']):
            raise ValueError('Exact officer compatibility receipt differs')
        receipt_path = ROOT / 'cases' / f'receipt-compat-{suffix}-primary.json'
        shutil.copyfile(compatible / 'compatibility.json', receipt_path)
        attempt = REPO / '.runtime-work' / f'c10365-{suffix}-primary-attempt-all'
        output = REPO / '.runtime-work' / f'c10365-{suffix}-primary-saved-all'
        materialize(MANIFEST, case_id, attempt)
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c10365-source-') as temporary:
            fixture = Path(temporary) / 'source'
            fixture_materialize(REPO, REPO / entry['fixture_recipe'], fixture)
            copy_sources(fixture, attempt)
        before = {path.relative_to(attempt).as_posix(): digest(path)
                  for path in attempt.rglob('*') if path.is_file()}
        saved_log = ROOT / 'cases' / f'case-saved-{suffix}.log'
        saved = command([sys.executable, str(REPO / 'runtime.py'), 'process-saved',
                         '--manifest', str(MANIFEST), '--case', case_id,
                         '--attempt', str(attempt), '--output', str(output),
                         '--library', str(REPO / 'runtime/library'),
                         '--validator', str(VALIDATOR)], saved_log)
        if (not saved.get('passed') or saved.get('case_id') != case_id
                or saved.get('candidate_id') != 'primary'
                or not saved.get('originals_preserved')
                or saved.get('physical_acceptance_claimed')
                or saved.get('legal_acceptance_claimed')
                or saved.get('native_revision', {}).get('construction_sha256') !=
                entry['construction_sha256']
                or any(digest(attempt / path) != value for path, value in before.items())):
            raise ValueError('Exact saved source/identity differs: ' + suffix)
        saved_path = ROOT / 'cases' / f'saved-{suffix}.json'
        saved_path.write_text(json.dumps(saved, indent=2) + '\n')
        records.append({'case_id': case_id,
                        'construction_sha256': entry['construction_sha256'],
                        'offline_log': str(offline_log.relative_to(ROOT)),
                        'offline_log_sha256': digest(offline_log),
                        'compatibility_log': str(compatibility_log.relative_to(ROOT)),
                        'compatibility_log_sha256': digest(compatibility_log),
                        'compatibility_receipt': str(receipt_path.relative_to(ROOT)),
                        'compatibility_receipt_sha256': digest(receipt_path),
                        'saved_log': str(saved_log.relative_to(ROOT)),
                        'saved_log_sha256': digest(saved_log),
                        'saved_receipt': str(saved_path.relative_to(ROOT)),
                        'saved_receipt_sha256': digest(saved_path),
                        'physical_acceptance_claimed': False,
                        'legal_acceptance_claimed': False})
        print('offline+compat+saved ' + suffix, flush=True)
    (ROOT / 'primary-proofs.json').write_text(json.dumps({
        'format': 'worker-officer-primary-cpu-proofs',
        'assignment_id': ROOT.name, 'manifest_sha256': digest(MANIFEST),
        'cases': records}, indent=2) + '\n')
    print('Four exact officer primary CPU paths pass', flush=True)


if __name__ == '__main__':
    main()
