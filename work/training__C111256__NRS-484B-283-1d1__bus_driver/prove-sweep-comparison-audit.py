"""Exercise four-source comparison and rejection of altered fixed conditions."""
import json
from pathlib import Path

import sweep_comparison_audit as audit

ROOT = audit.HERE.parents[1]
BASE = ROOT / '.runtime-work/c111256-update033-sweep-delivery'
MANIFEST = BASE / 'manifest/sweep-proof-bound-promotion-candidate.json'
ATTEMPTS = {key: BASE / key / 'attempt' for key in audit.SUFFIXES}
PROCESSING = {key: BASE / key / 'processed/v0001/processing.json'
              for key in audit.SUFFIXES}


def rejects(call, expected):
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise
    else:
        raise ValueError('Comparison accepted ' + expected)


def main():
    result = audit.compare(ATTEMPTS, PROCESSING, diagnostic=True,
                           manifest_path=MANIFEST)
    if (result['passed'] or result['diagnostic_source_shape_passed'] is not True or
            result['comparison_id'] != audit.HERE.name +
            '__right_of_way_physical_context_sweep'):
        raise ValueError('Synthetic sweep comparison claimed acceptance')
    rejects(lambda: audit.compare(ATTEMPTS, PROCESSING, manifest_path=MANIFEST),
            'Original Native Walk source required')
    original_read = audit.read
    def altered_config(path):
        item = original_read(path)
        if Path(path) == ATTEMPTS[audit.SUFFIXES[1]] / 'config.json':
            item['knobs']['crosswalk_hold_margin_m'] = 3.0
        return item
    audit.read = altered_config
    try:
        rejects(lambda: audit.compare(ATTEMPTS, PROCESSING, diagnostic=True,
                                      manifest_path=MANIFEST),
                'Sweep controller setpoints differ')
    finally:
        audit.read = original_read
    original_rows = audit.rows
    def altered_pedestrian(path):
        item = original_rows(path)
        if Path(path) == ATTEMPTS[audit.SUFFIXES[2]] / 'native_samples.jsonl':
            item[120]['pedestrian_body_xy_m'][0][0] += 1.0
        return item
    audit.rows = altered_pedestrian
    try:
        rejects(lambda: audit.compare(ATTEMPTS, PROCESSING, diagnostic=True,
                                      manifest_path=MANIFEST),
                'Sweep fixed pedestrian, Walk request or frame time differs')
    finally:
        audit.rows = original_rows
    print(json.dumps({'format': 'c111256-sweep-comparison-proof-v1',
                      'diagnostic_source_shape_passed': True,
                      'setpoints_m': result['setpoint_margin_m'],
                      'observed_margins_m': result['observed_margin_m'],
                      'negative_rejections': ['synthetic_original_promotion',
                                              'changed_setpoint', 'changed_pedestrian_body'],
                      'original_comparison_accepted': False}, sort_keys=True))


if __name__ == '__main__':
    main()
