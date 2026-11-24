"""Reject a drifted selected comparison without changing returned receipts."""
import importlib.util
from pathlib import Path


path = Path(__file__).with_name('audit-all-selected-comparisons.py')
spec = importlib.util.spec_from_file_location('selected_comparisons', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.audit()['selected_comparisons'] == 18
original_read = module.read


def drift(name):
    report = original_read(name)
    if name == 'current-ordinary-comparison-audit.json':
        report['comparisons'][0]['case_ids'] = report['comparisons'][1]['case_ids']
    return report


module.read = drift
try:
    module.audit()
except ValueError as error:
    assert 'Selected comparison cases differ' in str(error), error
else:
    raise AssertionError('Drifted ordinary comparison was accepted')
print('18 selected comparison bindings pass; changed exact case membership rejects')
