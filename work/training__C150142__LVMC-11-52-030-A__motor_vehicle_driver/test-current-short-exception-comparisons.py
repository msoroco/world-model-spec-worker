"""Reject a false current selected mail-activity contrast expectation."""
import importlib.util
from pathlib import Path

path = Path(__file__).with_name('audit-current-short-exception-comparisons.py')
spec = importlib.util.spec_from_file_location('current_short_comparisons', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original = module.PAIRS['mail_activity']
module.PAIRS['mail_activity'] = ('mail_deposit', False, True)
try:
    module.main()
except ValueError as error:
    assert 'Planned source contrast missing: mail_activity' in str(error)
else:
    raise AssertionError('False selected mail-activity contrast passed')
finally:
    module.PAIRS['mail_activity'] = original
print('false current mail-activity contrast rejected')
