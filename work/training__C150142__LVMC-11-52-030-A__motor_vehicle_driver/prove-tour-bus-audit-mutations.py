"""Exercise three independent rejection branches of the fallback audit."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('below_audit',
                                             ROOT / 'audit-tour-bus-below-fallbacks.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)
original_read = audit_module.read


def exercise(name, suffix, mutate, expected):
    def changed(path):
        value = original_read(path)
        if str(path).endswith(suffix):
            mutate(value)
        return value
    audit_module.read = changed
    try:
        try:
            audit_module.audit()
        except ValueError as error:
            if expected not in str(error):
                raise
            return {'mutation': name, 'rejected': True, 'error': str(error)}
        raise AssertionError('Audit accepted ' + name)
    finally:
        audit_module.read = original_read


if __name__ == '__main__':
    results = [
        exercise('changed_processing_sha',
                 'update032-below-fallback1-pinned-saved-v1.json',
                 lambda value: value.__setitem__('processing_sha256', '0' * 64),
                 'Full pinned CPU proof differs'),
        exercise('changed_fixed_boundary',
                 'below-fallback2-result-v1/v0001/analysis/config.json',
                 lambda value: value.__setitem__('requested_boundary', 'above'),
                 'Fixed law-boundary configuration differs'),
        exercise('duplicate_physical_trigger',
                 'execution-manifest-diagnostic-tour_bus_below-draft.json',
                 lambda value: value['cases'][0]['candidates'][1].__setitem__(
                     'trigger', value['cases'][0]['candidates'][0]['trigger']),
                 'Fallback physical-risk triggers overlap'),
    ]
    print(json.dumps({'format': 'c150142-below-fallback-audit-mutations-v1',
                      'passed': True, 'results': results}, sort_keys=True))
