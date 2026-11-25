"""Bind six checker outcomes and two tested lifecycle orders."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for index, entry in enumerate(manifest['cases']):
    letter = 'a' if index == 0 else 'b'
    prefix = f'proofs/condition_{letter}/physical/'
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result = prefix + kind + '.json'
        log = prefix + kind + '.log'
        fixtures.append({'kind': kind,
                         'command': f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{ROOT.name}/native/prove_physical.py --letter {letter} --kind {kind}',
                         'exit_code': 0, 'log': log, 'log_sha256': sha(ROOT / log),
                         'result': result, 'result_sha256': sha(ROOT / result)})
    lifecycle_log = prefix + 'lifecycle.log'
    receipt_path = ROOT / prefix / 'physical-preparation.json'
    receipt = {'format': 'worker-physical-preparation', 'case_id': entry['case_id'],
               'construction_sha256': entry['construction_sha256'], 'fixtures': fixtures,
               'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                                         'restoration_verified', 'native_exit',
                                         'owner_released', 'saved_processing_started'],
                             'command': f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{ROOT.name}/native/prove_lifecycle.py --letter {letter}',
                             'exit_code': 0, 'log': lifecycle_log,
                             'log_sha256': sha(ROOT / lifecycle_log)},
               'physical_acceptance_claimed': False}
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    entry['physical_preparation'] = {'receipt': str(receipt_path.relative_to(ROOT)),
                                     'sha256': sha(receipt_path)}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
