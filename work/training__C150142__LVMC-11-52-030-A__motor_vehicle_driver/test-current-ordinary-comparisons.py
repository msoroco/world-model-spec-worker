"""Reject a deliberately inverted ordinary source contrast."""
import importlib.util
from pathlib import Path

script = Path(__file__).with_name('audit-current-ordinary-comparisons.py')
spec = importlib.util.spec_from_file_location('ordinary_audit', script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.audit()['passed'] is True
module.EXPECTED_MAIN = (False, True)
try:
    module.audit()
except ValueError as error:
    assert 'Main red-curb source contrast missing' in str(error)
else:
    raise AssertionError('Inverted source contrast was accepted')
print('ordinary comparisons: positive and inverted-contrast negative passed')
