"""Run positive and altered-identity selected comparison CPU audits."""
import hashlib
import importlib.util
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
SOURCE = FOLDER / 'audit-selected-comparison.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


spec = importlib.util.spec_from_file_location('selected_comparison', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
positive = module.audit()
assert positive['passed'] is True
saved = json.loads((FOLDER / 'current-v5-true-primary-saved-processing.json').read_text())
altered = dict(saved, case_id=positive['cases']['false']['case_id'])
try:
    module.audit({'true': altered})
except ValueError as error:
    assert 'Saved receipt case/candidate mismatch' in str(error), str(error)
    rejected_error = str(error)
else:
    raise AssertionError('Changed selected case identity was accepted')
receipt = {
    'format': 'c111088-selected-comparison-cpu-proof-v1',
    'passed': True,
    'audit_script': SOURCE.name,
    'audit_script_sha256': sha(SOURCE),
    'positive': positive,
    'negative': {'mutation': 'true saved receipt case_id replaced with false case_id',
                 'rejected': True, 'error': rejected_error},
    'scope': 'synthetic CPU diagnostic only; no original Native or pixel review',
}
target = FOLDER / 'selected-comparison-cpu-proof.json'
target.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
print(json.dumps({'passed': True, 'positive_cases': len(positive['cases']),
                  'altered_identity_rejected': True, 'receipt_sha256': sha(target)}))
