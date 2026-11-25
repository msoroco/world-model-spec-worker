"""Verify production Native operator cannot start without its source seal."""
import os
from runner import _operator

for key in ('SCENARIO_C111329_ORIGINAL_OPERATOR',
            'SCENARIO_C111329_ORIGINAL_OPERATOR_SHA256'):
    os.environ.pop(key, None)
try:
    _operator()
except ValueError as exc:
    assert str(exc) == 'source-reviewed C111329 Native operator is required'
    print('expected rejection:', exc)
else:
    raise AssertionError('source-unbound production operator accepted')
