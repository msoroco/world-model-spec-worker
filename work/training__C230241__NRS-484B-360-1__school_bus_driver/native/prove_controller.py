import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('controller', Path(__file__).with_name('controller.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

low = module.control('probe_a', [0, 0, 0])
high = module.control('probe_b', [0, 0, 0])
assert high['requested_speed_mps'] > low['requested_speed_mps']
assert low['throttle'] > 0 and high['throttle'] > 0
assert module.control('probe_a', [30, 0, 0])['brake'] > 0
assert module.control('probe_b', [30, 0, 0])['brake'] > 0
for bad in ([float('nan'), 0, 0], [1, 2], [float('inf'), 0, 0]):
    try:
        module.control('probe_a', bad)
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid velocity accepted')
print(json.dumps({'passed': True, 'requested_mph': module.REQUEST_MPH,
                  'requests_distinct': True, 'post_tick_feedback_tested': True,
                  'physical_realization_claimed': False}, indent=2))
