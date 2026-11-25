"""Reject a fallback that changes statutory or capture conditions."""

import importlib.util
from pathlib import Path


script = Path(__file__).with_name('audit-current-candidate-isolation.py')
spec = importlib.util.spec_from_file_location('candidate_isolation', script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

positive = module.audit()
assert positive['passed'] and positive['selected_cases'] == 30


def reject(field, value, expected):
    def changed(case_id, candidate_id, config):
        if case_id.endswith('__tour_bus_below') and candidate_id == 'fallback1':
            config[field] = value
    try:
        module.audit(changed)
    except ValueError as error:
        assert expected in str(error), (field, error)
    else:
        raise AssertionError('Changed fallback accepted: ' + field)


reject('service_class', 'limousine', 'fixed conditions differ')
reject('capture_frames', 120, 'fixed conditions differ')
reject('requested_target_x_m', 60, 'changed red-curb comparison')
print('30 selected cases and fallback scope, capture, and curb-relation negatives passed')
