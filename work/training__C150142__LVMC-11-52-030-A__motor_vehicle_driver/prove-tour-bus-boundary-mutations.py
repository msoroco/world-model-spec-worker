"""Verify the comparison rejects changed duration, activity and fixed actor."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('boundary_audit',
                                             ROOT / 'audit-tour-bus-boundaries.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original_read = module.read


def reject(name, suffix, mutate, expected):
    def changed(path):
        value = original_read(path)
        if str(path).endswith(suffix):
            mutate(value)
        return value
    module.read = changed
    try:
        try:
            module.audit()
        except ValueError as error:
            if expected not in str(error):
                raise
            return {'mutation': name, 'rejected': True, 'error': str(error)}
        raise AssertionError('Comparison accepted ' + name)
    finally:
        module.read = original_read


if __name__ == '__main__':
    outcomes = [
        reject('changed_at_duration', 'update033-tour-bus-at-primary-recheck.json',
               lambda v: v.__setitem__('reported_duration_s', 1799.95),
               'Pinned primary or negative proof differs'),
        reject('invented_no_loading_event',
               'update033-tour-bus-no-loading-primary-recheck.json',
               lambda v: v.__setitem__('reported_activity_events', 1),
               'Pinned primary or negative proof differs'),
        reject('changed_fixed_actor', 'at-v1/config.json',
               lambda v: v.__setitem__('native_blueprint', 'vehicle.other'),
               'Fixed scene or map source differs'),
    ]
    print(json.dumps({'format': 'c150142-tour-bus-boundary-mutations-v1',
                      'passed': True, 'results': outcomes}, sort_keys=True))
