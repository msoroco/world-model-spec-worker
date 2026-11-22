"""Check current selected Walk comparison and fixed-source rejection."""
import json
from pathlib import Path

import comparison_audit as module
from current_runtime_attempt import locate

ROOT = module.HERE.parents[1]


def pair(suffix):
    attempt = locate(suffix)
    processing = attempt.parent / (attempt.name.removesuffix("-compat") + "-saved") / "v0001/processing.json"
    retained = module.HERE / "current-runtime-selected-proof" / suffix / "primary/saved-processing.json"
    if module.sha(processing) != module.sha(retained):
        raise ValueError("Current saved comparison receipt differs")
    return attempt, processing


def reject(call, expected):
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise
    else:
        raise ValueError('Comparison accepted ' + expected)


def main():
    ref, ref_processing = pair('reference')
    con, con_processing = pair('contrast')
    result = module.compare(ref, ref_processing, con, con_processing, diagnostic=True)
    if result['passed'] or result['changed_bus_body_frames'] != 70:
        raise ValueError('Synthetic selected comparison scope differs')
    reject(lambda: module.compare(ref, ref_processing, con, con_processing),
           'Original Native Walk source required')
    original_rows = module.rows
    def altered(path):
        data = original_rows(path)
        if Path(path) == con / 'native_samples.jsonl':
            data[135]['pedestrian_body_xy_m'][0][0] += 1.0
        return data
    module.rows = altered
    try:
        reject(lambda: module.compare(ref, ref_processing, con, con_processing,
                                      diagnostic=True),
               'Controlled pedestrian, Walk request or sampled time differs')
    finally:
        module.rows = original_rows
    print(json.dumps({'format': 'c111256-independent-comparison-cpu-proof-v1',
                      'diagnostic_pair_checked': True,
                      'changed_bus_body_frames': result['changed_bus_body_frames'],
                      'negative_rejections': ['synthetic_original_promotion',
                                              'pedestrian_fixed_condition_changed'],
                      'original_comparison_accepted': False}, sort_keys=True))


if __name__ == '__main__':
    main()
