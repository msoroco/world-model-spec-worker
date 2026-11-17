"""Reject corrupt text-6 emergency business comparison claims."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('pair_audit',
                                            ROOT / 'audit-emergency-business-pair.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def reject(name, configs=None, summaries=None):
    try:
        AUDIT.check(config_overrides=configs, summary_overrides=summaries)
    except ValueError as error:
        return {'mutation': name, 'rejected': True, 'reason': str(error)}
    raise AssertionError('Corrupt business comparison accepted: ' + name)


def prove():
    AUDIT.check()
    outputs = []
    _, _, config = AUDIT.package(AUDIT.BUSINESS, 'primary')
    changed = copy.deepcopy(config)
    changed['requested_stationary_duration_s'] = 13
    outputs.append(reject('changed_fixed_duration',
                          configs={(AUDIT.BUSINESS, 'primary'): changed}))
    _, _, config = AUDIT.package(AUDIT.NO_WORKER, 'fallback2')
    changed = copy.deepcopy(config)
    changed['camera_policy'] = 'standard'
    outputs.append(reject('changed_fixed_camera',
                          configs={(AUDIT.NO_WORKER, 'fallback2'): changed}))
    source = json.loads((ROOT / 'update040-emergency-no-business-saved-matrix.json').read_text())
    changed = copy.deepcopy(source)
    changed['candidates'][1]['frames'] = 360
    outputs.append(reject('changed_saved_frame_count',
                          summaries={AUDIT.NO_WORKER: changed}))
    changed = copy.deepcopy(source)
    changed['candidates'][0]['actual_business_absence_established'] = True
    outputs.append(reject('invented_business_absence',
                          summaries={AUDIT.NO_WORKER: changed}))
    return {'comparison_id': AUDIT.BASE + '__emergency_vehicle_unsigned_business_pair',
            'negative_checks': outputs}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
