"""Exercise three independent rejection branches of the fallback audit."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('below_audit',
                                             ROOT / 'audit-tour-bus-below-fallbacks.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)
original_read = audit_module.read


def exercise(name, path_suffix, mutate, expected, boundary, service='tour_bus'):
    def changed(path):
        value = original_read(path)
        if str(path).endswith(path_suffix):
            mutate(value)
        return value
    audit_module.read = changed
    try:
        try:
            audit_module.audit(boundary, service)
        except ValueError as error:
            if expected not in str(error):
                raise
            return {'mutation': name, 'rejected': True, 'error': str(error)}
        raise AssertionError('Audit accepted ' + name)
    finally:
        audit_module.read = original_read


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('below', 'at', 'above', 'no_loading'), default='below')
    parser.add_argument('--service', choices=('tour_bus', 'shuttle_bus'),
                        default='tour_bus')
    args = parser.parse_args()
    boundary = args.case
    service = args.service
    update = {'below': '032', 'at': '033', 'above': '034',
              'no_loading': '034'}[boundary]
    slug = boundary.replace('_', '-')
    def duplicate_trigger(value):
        entry = next(e for e in value['cases'] if e['case_id'].endswith(service + '_' + boundary))
        entry['candidates'][1]['trigger'] = entry['candidates'][0]['trigger']
    summary_path = ((f'update035-shuttle-below-fallback1-pinned-saved-v1.json'
                     if boundary == 'below' else
                     f'update036-shuttle-{slug}-fallback1-pinned-saved-v1.json')
                    if service == 'shuttle_bus' else
                    f'update{update}-{slug}-fallback1-pinned-saved-v1.json')
    config_path = (f'shuttle-{slug}-fallback2-result-v1/v0001/analysis/config.json'
                   if service == 'shuttle_bus' else
                   f'{slug}-fallback2-result-v1/v0001/analysis/config.json')
    manifest_path = ('execution-manifest-diagnostic-shuttle_bus_below-draft.json'
                     if service == 'shuttle_bus' else
                     'execution-manifest-diagnostic-tour_bus_below-draft.json')
    results = [
        exercise('changed_processing_sha',
                 summary_path,
                 lambda value: value.__setitem__('processing_sha256', '0' * 64),
                 'Full pinned CPU proof differs', boundary, service),
        exercise('changed_fixed_boundary',
                 config_path,
                 lambda value: value.__setitem__('requested_boundary',
                                                  'below' if boundary == 'above' else 'above'),
                 'Fixed law-boundary configuration differs', boundary, service),
        exercise('duplicate_physical_trigger',
                 manifest_path,
                 duplicate_trigger,
                 'Fallback physical-risk triggers overlap', boundary, service),
    ]
    print(json.dumps({'format': 'c150142-' +
                      ('shuttle-' if service == 'shuttle_bus' else '') +
                      boundary + '-fallback-audit-mutations-v1',
                      'passed': True, 'results': results}, sort_keys=True))
