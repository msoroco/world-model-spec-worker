"""Reject missing and stale evidence in the independent signed audit."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('signed_audit',
                                              ROOT / 'audit-signed-current.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


def rejected(index, expected):
    try:
        audit_module.audit(index)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f'Wrong signed audit rejection: {error}') from error
    else:
        raise AssertionError('Signed audit accepted mutation: ' + expected)


def prove():
    original = json.loads((ROOT /
        'selected-ordinary_red_signed-current-receipts/proof-index.json').read_text())
    audit_module.audit(original)
    missing = copy.deepcopy(original)
    del missing['candidates']['fallback3']
    rejected(missing, 'candidate index')
    stale_source = copy.deepcopy(original)
    stale_source['candidates']['primary']['construction_sha256'] = '0' * 64
    rejected(stale_source, 'source hash')
    stale_receipt = copy.deepcopy(original)
    stale_receipt['candidates']['fallback1']['receipts']['negative_analysis']['sha256'] = '0' * 64
    rejected(stale_receipt, 'receipt changed')
    altered_measurement = copy.deepcopy(original)
    altered_measurement['candidates']['fallback2']['synthetic_red_stopped_frames'] = 0
    rejected(altered_measurement, 'stopped interval')
    return {'format': 'c150142-signed-audit-negative-proof-v1',
            'passed': True, 'mutations_rejected': 4}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
