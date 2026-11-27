"""Diagnose the frozen supplemental import lookup without changing returned status."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path('runtime').resolve()))
from scenario_pipeline.worker_exchange import preparation

ASSIGNMENT = 'testing__C230221__NRS-484B-280-1c__motor_vehicle_driver'
original_read = preparation.read


def virtual_ready(path):
    value = original_read(path)
    if str(path).endswith('work/' + ASSIGNMENT + '/result.json'):
        return {**value, 'status': 'ready'}
    return value


preparation.read = virtual_ready
try:
    preparation.check(Path.cwd(), complete=True, require_ready=True, assignment=ASSIGNMENT)
except FileNotFoundError as error:
    expected = Path.cwd() / 'inputs' / ASSIGNMENT / 'assignment.json'
    if Path(error.filename) != expected:
        raise
    print('expected frozen lookup failure: ' + str(expected.relative_to(Path.cwd())))
else:
    raise AssertionError('unpatched supplemental import lookup unexpectedly passed')
finally:
    preparation.read = original_read
