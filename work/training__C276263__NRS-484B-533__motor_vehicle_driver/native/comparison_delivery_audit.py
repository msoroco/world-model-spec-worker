"""Independent pair audit for two reviewed original graded-standing attempts."""
import json
from pathlib import Path

from comparison import compare, isolated_duty_contrast
from delivery_audit import audit_attempt
from instrument_producer import digest

ASSIGNMENT = 'training__C276263__NRS-484B-533__motor_vehicle_driver'
REFERENCE = ASSIGNMENT + '__reference'
CONTRAST = ASSIGNMENT + '__contrast'
ISOLATED = {'engine_on': 'engine_operation',
            'brake_unset': 'parking_brake_state',
            'wheel_straight': 'front_wheel_orientation'}


def audit_pair(reference, contrast, reference_review, contrast_review,
               contrast_case='contrast'):
    if contrast_case not in ('contrast', *ISOLATED):
        raise ValueError('Unknown exact contrast case')
    contrast_id = ASSIGNMENT + '__' + contrast_case
    reference, contrast = Path(reference).resolve(), Path(contrast).resolve()
    if reference == contrast:
        raise ValueError('Independent original attempts required')
    left_audit = audit_attempt(reference, REFERENCE, reference_review)
    right_audit = audit_attempt(contrast, contrast_id, contrast_review)
    left_instrument = json.loads((reference / 'instrument-audit.json').read_text())
    right_instrument = json.loads((contrast / 'instrument-audit.json').read_text())
    if (left_instrument['calibration_sha256'] != right_instrument['calibration_sha256'] or
            left_instrument['source_sensor_ids'] != right_instrument['source_sensor_ids']):
        raise ValueError('Original curb calibration or instrument source differs')
    left_hashes = json.loads((reference / 'acquisition-hashes.json').read_text())
    right_hashes = json.loads((contrast / 'acquisition-hashes.json').read_text())
    comparison = (compare(reference, contrast, left_hashes, right_hashes)
                  if contrast_case == 'contrast' else
                  isolated_duty_contrast(reference, contrast, left_hashes,
                                         right_hashes, ISOLATED[contrast_case]))
    if (comparison['source_kind'] != 'original_native' or
            not all(comparison['fixed_checks'].values()) or
            (contrast_case == 'contrast' and
             not all(comparison['difference_checks'].values()))):
        raise ValueError('Reviewed original fixed-condition comparison absent')
    return {'format': 'c276263-reviewed-original-comparison-v1',
            'reference_case_id': REFERENCE,
            'contrast_case_id': contrast_id,
            'passed': True,
            'reference_delivery_audit_sha256': digest(left_audit),
            'contrast_delivery_audit_sha256': digest(right_audit),
            'fixed_instrument_calibration_sha256':
                left_instrument['calibration_sha256'],
            'comparison': comparison,
            'legal_verdict': None}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', required=True)
    parser.add_argument('--contrast', required=True)
    parser.add_argument('--reference-review', required=True)
    parser.add_argument('--contrast-review', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--contrast-case', default='contrast',
                        choices=['contrast', *ISOLATED])
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Use fresh independent comparison output')
    result = audit_pair(args.reference, args.contrast,
                        args.reference_review, args.contrast_review,
                        args.contrast_case)
    output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
