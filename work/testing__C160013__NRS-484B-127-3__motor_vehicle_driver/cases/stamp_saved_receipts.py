"""Retain recorded-only source rebuild receipts for the selected pair."""
import hashlib
import json
import shutil
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
manifest_path = PACKAGE / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for label, suffix in (('wide', 'entrant_can_occupy_gap'),
                      ('narrow', 'entrant_cannot_occupy_gap')):
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + suffix))
    result = REPO / '.runtime-work' / ('c160013-' + label + '-saved-v2/v0001/processing.json')
    command_log = REPO / '.runtime-work' / ('c160013-' + label + '-saved-v2-command.log')
    receipt_path = PACKAGE / 'cases' / (suffix + '-saved-receipt.json')
    log_path = PACKAGE / 'cases' / (suffix + '-saved-command.log')
    shutil.copyfile(result, receipt_path)
    shutil.copyfile(command_log, log_path)
    value = json.loads(receipt_path.read_text())
    if value.get('passed') is not True or value.get('recorded_only') is not True or value.get('case_id') != entry['case_id']:
        raise ValueError('Recorded-only proof did not pass for ' + suffix)
    entry['saved_processing'] = {
        'command': 'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved --manifest work/' +
                   PACKAGE.name + '/execution-manifest.json --case ' + entry['case_id'] +
                   ' --attempt .runtime-work/c160013-' + label + '-saved-source-v2' +
                   ' --output .runtime-work/c160013-' + label + '-saved-v2' +
                   ' --library runtime/library --validator .runtime-work/c215286-current-decoder/.lake/build/bin/adapterCheck',
        'receipt': 'cases/' + receipt_path.name, 'sha256': sha(receipt_path),
        'log': 'cases/' + log_path.name, 'log_sha256': sha(log_path)}
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print('Retained both recorded-only rebuild receipts')
