"""Bind current full-duration diagnostic audit receipts for the approaching pair."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for name, branch in (('approaching_yield', 'yield'), ('approaching_no_yield', 'proceed')):
    folder = root / 'cases' / name
    path = folder / 'delivery-diagnostic.json'
    receipt = json.loads(path.read_text())
    positive = json.loads((folder / 'delivery-positive.log').read_text())
    negative = (folder / 'delivery-negative.log').read_text()
    assert receipt['case_id'] == f'{root.name}__{name}'
    assert receipt['approaching_sequence']['branch'] == branch
    assert receipt['frames'] == 900 and receipt['software_checks_passed'] is True
    assert receipt['passed'] is False and receipt['diagnostic_fixture'] is True
    assert receipt['physical_acceptance_claimed'] is False
    assert receipt['auditor_sha256'] == sha(root / 'approaching_delivery_audit.py')
    assert positive['audit_sha256'] == sha(path)
    assert 'Sealed original source changed: interaction_history.jsonl' in negative
    print(json.dumps({'case_id': receipt['case_id'], 'frames': 900,
                      'software_checks_passed': True,
                      'missing_original_rejected': True,
                      'delivery_passed': False,
                      'audit_sha256': sha(path)}))
