"""Exercise independent selected delivery diagnostic and rejection paths."""
import json
from pathlib import Path

from delivery_audit import audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def paths(suffix):
    base = ROOT / '.runtime-work/c111256-update024-selected' / suffix / 'primary'
    return base / 'selected-attempt', base / 'processed/v0001/processing.json'


def reject(call, expected):
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise
    else:
        raise ValueError('Independent delivery audit accepted ' + expected)


def main():
    results = []
    for suffix in ('reference', 'contrast'):
        case = HERE.name + '__' + suffix
        attempt, processing = paths(suffix)
        value = audit(case, 'primary', attempt, processing, diagnostic=True)
        if (value['passed'] is not False or value['source_shaped_unit_test'] is not True or
                any(value['checks'].values()) or
                set(value['source_frame_counts'].values()) != {480}):
            raise ValueError('Synthetic source was promoted to delivery acceptance')
        reject(lambda: audit(case, 'primary', attempt, processing),
               'Original Native Walk source required')
        other = 'contrast' if suffix == 'reference' else 'reference'
        reject(lambda: audit(case, 'primary', attempt, paths(other)[1], diagnostic=True),
               'Saved processing chain incomplete')
        results.append({'case_id': case, 'diagnostic_source_shape_passed': True,
                        'original_promotion_rejected': True,
                        'wrong_processing_receipt_rejected': True,
                        'original_delivery_accepted': False})
    print(json.dumps({'format': 'c111256-independent-delivery-cpu-proof-v1',
                      'cases': results, 'negative_rejections': 4,
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
