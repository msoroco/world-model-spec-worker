"""Reject stale evidence, a changed scene, and overlapping fallback risks."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'ordinary_saved_audit', ROOT / 'audit-ordinary-red-saved-update037.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original = module.read


def exercise(name, suffix, mutate, expected):
    def altered(path):
        value = original(path)
        if str(path).endswith(suffix):
            mutate(value)
        return value

    module.read = altered
    try:
        try:
            module.audit()
        except ValueError as error:
            if expected not in str(error):
                raise
            return {'mutation': name, 'rejected': True, 'error': str(error)}
        raise AssertionError('Audit accepted ' + name)
    finally:
        module.read = original


if __name__ == '__main__':
    results = [
        exercise('stale_processing_hash',
                 'update037-ordinary-red-fallback1-pinned-saved.json',
                 lambda value: value.__setitem__('processing_sha256', '0' * 64),
                 'Full CPU saved proof differs'),
        exercise('changed_sign_class',
                 'c150142-ordinary-red-fallback2-saved-result-update037/v0001/analysis/config.json',
                 lambda value: value.__setitem__('sign_classes', ['tour_bus']),
                 'Fixed signed-curb scene differs'),
        exercise('duplicate_physical_risk',
                 'execution-manifest-diagnostic-ordinary_red_signed.json',
                 lambda value: value['cases'][0]['candidates'][1].__setitem__(
                     'trigger', value['cases'][0]['candidates'][0]['trigger']),
                 'Physical-risk triggers overlap'),
    ]
    print(json.dumps({'format': 'c150142-ordinary-red-saved-audit-mutations-v1',
                      'passed': True, 'results': results}, sort_keys=True))
