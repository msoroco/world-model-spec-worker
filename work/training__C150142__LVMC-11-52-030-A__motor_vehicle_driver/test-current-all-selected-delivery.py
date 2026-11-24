"""Reject a stale ordinary camera decode receipt after a passing audit."""
import importlib.util
from pathlib import Path

script = Path(__file__).with_name('audit-current-all-selected-delivery.py')
spec = importlib.util.spec_from_file_location('selected_delivery', script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.audit()['selected_cases'] == 30
read = module.read


def stale(path):
    value = read(path)
    if Path(path).name == 'current-reference-primary-saved-source-0.json':
        value['mapping_sha256'] = '0' * 64
    return value


module.read = stale
try:
    module.audit()
except ValueError as error:
    assert 'Ordinary full source decode differs: reference' in str(error)
else:
    raise AssertionError('Stale camera mapping was accepted')
print('30 selected positive and stale ordinary camera mapping negative passed')
