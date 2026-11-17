"""Verify the cross-boundary audit rejects altered source-bound comparisons."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('limo_boundary_audit',
                                             ROOT / 'audit-limo-v2-boundaries.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def reject(name, suffix, mutate, expected):
    def loader(path):
        value = MODULE.read(path)
        if str(path).endswith(suffix):
            value = copy.deepcopy(value)
            mutate(value)
        return value
    try:
        MODULE.audit(loader)
    except ValueError as error:
        if expected not in str(error):
            raise
        return {'mutation': name, 'rejected': True, 'error': str(error)}
    raise AssertionError('Boundary audit accepted ' + name)


def prove():
    valid = MODULE.audit()
    if not valid['passed'] or valid['candidate_count'] != 16:
        raise ValueError('Positive boundary audit differs')
    rejected = [
        reject('below_duration',
               'update038-limo-below-primary-pinned-saved-v2.json',
               lambda row: row.__setitem__('reported_duration_s', 1800),
               'Statutory boundary observation differs'),
        reject('no_loading_activity',
               'update038-limo-no-loading-primary-pinned-saved-v2.json',
               lambda row: row.__setitem__('reported_activity_events', 1),
               'Statutory boundary observation differs'),
        reject('changed_fixed_camera',
               'c150142-limo-above-primary-result-v2/v0001/analysis/config.json',
               lambda row: row.__setitem__('camera_policy', {'invented': True}),
               'Cross-boundary fixed conditions differ'),
        reject('missing_local_binding',
               'update038-limo-at-fallback-audit-v2.json',
               lambda row: row.__setitem__('manifest_sha256', '0' * 64),
               'Boundary fallback audit is incomplete'),
    ]
    return {'format': 'c150142-limo-v2-boundary-comparison-mutations',
            'passed': True, 'manifest_sha256': valid['manifest_sha256'],
            'rejected': rejected}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
