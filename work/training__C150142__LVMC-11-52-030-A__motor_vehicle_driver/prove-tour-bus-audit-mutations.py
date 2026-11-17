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


def exercise(name, path_suffix, mutate, expected, boundary, service='tour_bus',
             manifest_version=1):
    def changed(path):
        value = original_read(path)
        if str(path).endswith(path_suffix):
            mutate(value)
        return value
    audit_module.read = changed
    try:
        try:
            audit_module.audit(boundary, service, manifest_version)
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
    parser.add_argument('--service', choices=('tour_bus', 'shuttle_bus', 'rtc_bus', 'limo'),
                        default='tour_bus')
    parser.add_argument('--manifest-version', type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    boundary = args.case
    service = args.service
    manifest_version = args.manifest_version
    if manifest_version == 2 and service != 'limo':
        raise ValueError('Only limousine cases have a corrected v2 draft')
    update = {'below': '032', 'at': '033', 'above': '034',
              'no_loading': '034'}[boundary]
    slug = boundary.replace('_', '-')
    def duplicate_trigger(value):
        entry = next(e for e in value['cases'] if e['case_id'].endswith(service + '_' + boundary))
        entry['candidates'][1]['trigger'] = entry['candidates'][0]['trigger']
    summary_path = (f'update038-limo-{slug}-fallback1-pinned-saved-v{manifest_version}.json'
                    if service == 'limo' else
                    f'update037-rtc-{slug}-fallback1-pinned-saved-v1.json'
                    if service == 'rtc_bus' else
                    (f'update035-shuttle-below-fallback1-pinned-saved-v1.json'
                     if boundary == 'below' else
                     f'update{"036" if boundary == "at" else "037"}-shuttle-{slug}-fallback1-pinned-saved-v1.json')
                    if service == 'shuttle_bus' else
                    f'update{update}-{slug}-fallback1-pinned-saved-v1.json')
    config_path = ({'tour_bus': f'{slug}-',
                    'shuttle_bus': f'shuttle-{slug}-',
                    'rtc_bus': f'rtc-{slug}-',
                    'limo': f'limo-{slug}-'}[service] +
                   f'fallback2-result-v{manifest_version}/v0001/analysis/config.json')
    manifest_path = {
        'tour_bus': 'execution-manifest-diagnostic-tour_bus_below-draft.json',
        'shuttle_bus': 'execution-manifest-diagnostic-shuttle_bus_below-draft.json',
        'rtc_bus': 'execution-manifest-diagnostic-rtc_bus_below-draft.json',
        'limo': 'execution-manifest-diagnostic-limo_below-draft.json',
    }[service]
    if manifest_version == 2:
        manifest_path = 'execution-manifest-diagnostic-limo_below-draft-v2.json'
    results = [
        exercise('changed_processing_sha',
                 summary_path,
                 lambda value: value.__setitem__('processing_sha256', '0' * 64),
                 'Full pinned CPU proof differs', boundary, service, manifest_version),
        exercise('changed_fixed_boundary',
                 config_path,
                 lambda value: value.__setitem__('requested_boundary',
                                                  'below' if boundary == 'above' else 'above'),
                 'Fixed law-boundary configuration differs', boundary, service,
                 manifest_version),
        exercise('duplicate_physical_trigger',
                 manifest_path,
                 duplicate_trigger,
                 'Fallback physical-risk triggers overlap', boundary, service,
                 manifest_version),
    ]
    print(json.dumps({'format': 'c150142-' +
                      (service.replace('_bus', '') + '-' if service != 'tour_bus' else '') +
                      boundary + f'-fallback-audit-mutations-v{manifest_version}',
                      'passed': True, 'manifest_version': manifest_version,
                      'results': results}, sort_keys=True))
