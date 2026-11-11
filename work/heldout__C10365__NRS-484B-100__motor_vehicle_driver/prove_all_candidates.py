"""Reprove exact officer primaries and three alternatives under one manifest."""

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
    return sha256(path.read_bytes()).hexdigest()


def run(args, log):
    proc = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    log.write_text(proc.stdout + proc.stderr)
    if proc.returncode:
        raise ValueError('Exact officer proof failed: ' + str(log))
    return json.loads(proc.stdout)


def main():
    manifest = json.loads(MANIFEST.read_text())
    records = []
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.split('__')[-1]
        for candidate in ({'id': 'primary', 'construction_sha256': entry['construction_sha256']},
                          *entry['candidates']):
            ident = candidate['id']
            label = suffix + '-' + ident
            args = ['--manifest', str(MANIFEST), '--case', case_id]
            if ident != 'primary':
                args += ['--candidate', ident]
            offline_log = ROOT / 'cases' / f'case-offline-{label}.log'
            off = run([sys.executable, str(REPO / 'runtime.py'), 'offline', *args,
                       '--output', str(REPO / '.runtime-work' / f'c10365-{label}-offline-v2'),
                       '--python', sys.executable], offline_log)
            if not off.get('offline_passed'):
                raise ValueError('Offline construction failed: ' + label)
            compatibility_log = ROOT / 'cases' / f'case-compat-{label}.log'
            compat_output = REPO / '.runtime-work' / f'c10365-{label}-compat-v2'
            compatible = run([sys.executable, str(REPO / 'runtime.py'), 'compatibility', *args,
                              '--output', str(compat_output), '--library', str(REPO / 'runtime/library'),
                              '--validator', str(VALIDATOR)], compatibility_log)
            if (not compatible.get('passed') or compatible.get('case_id') != case_id
                    or compatible.get('construction_sha256') != candidate['construction_sha256']):
                raise ValueError('Compatibility binding differs: ' + label)
            receipt_path = ROOT / 'cases' / f'receipt-compat-{label}.json'
            shutil.copyfile(compat_output / 'compatibility.json', receipt_path)
            record = {'case_id': case_id, 'candidate_id': ident,
                      'construction_sha256': candidate['construction_sha256'],
                      'offline_log': str(offline_log.relative_to(ROOT)),
                      'offline_log_sha256': digest(offline_log),
                      'compatibility_log': str(compatibility_log.relative_to(ROOT)),
                      'compatibility_log_sha256': digest(compatibility_log),
                      'compatibility_receipt': str(receipt_path.relative_to(ROOT)),
                      'compatibility_receipt_sha256': digest(receipt_path)}
            if ident == 'primary':
                attempt = REPO / '.runtime-work' / f'c10365-{suffix}-saved-attempt-v2'
                saved_output = REPO / '.runtime-work' / f'c10365-{suffix}-saved-output-v2'
                materialize(MANIFEST, case_id, attempt)
                with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c10365-source-') as temporary:
                    fixture = Path(temporary) / 'source'
                    fixture_materialize(REPO, REPO / entry['fixture_recipe'], fixture)
                    copy_sources(fixture, attempt)
                before = {p.relative_to(attempt).as_posix(): digest(p)
                          for p in attempt.rglob('*') if p.is_file()}
                saved_log = ROOT / 'cases' / f'case-saved-{suffix}.log'
                saved = run([sys.executable, str(REPO / 'runtime.py'), 'process-saved', *args,
                             '--attempt', str(attempt), '--output', str(saved_output),
                             '--library', str(REPO / 'runtime/library'), '--validator', str(VALIDATOR)], saved_log)
                if (not saved.get('passed') or saved.get('candidate_id') != 'primary'
                        or saved.get('physical_acceptance_claimed') or saved.get('legal_acceptance_claimed')
                        or not saved.get('originals_preserved')
                        or saved.get('native_revision', {}).get('construction_sha256') != candidate['construction_sha256']
                        or any(digest(attempt / path) != value for path, value in before.items())):
                    raise ValueError('Saved source/identity differs: ' + label)
                saved_path = ROOT / 'cases' / f'saved-{suffix}.json'
                saved_path.write_text(json.dumps(saved, indent=2) + '\n')
                record.update({'saved_log': str(saved_log.relative_to(ROOT)),
                               'saved_log_sha256': digest(saved_log),
                               'saved_receipt': str(saved_path.relative_to(ROOT)),
                               'saved_receipt_sha256': digest(saved_path)})
            records.append(record)
            print('offline+compat' + ('+saved ' if ident == 'primary' else ' ') + label, flush=True)
    (ROOT / 'candidate-proofs.json').write_text(json.dumps({
        'format': 'worker-officer-candidate-cpu-proofs', 'assignment_id': ROOT.name,
        'manifest_sha256': digest(MANIFEST), 'cases': records}, indent=2) + '\n')
    print('All 16 exact officer construction candidates pass', flush=True)


if __name__ == '__main__':
    main()
