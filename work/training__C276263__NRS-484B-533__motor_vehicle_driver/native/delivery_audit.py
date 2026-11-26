"""Independent original-source delivery audit for unattended graded standing.

This does not decide law. It requires a separate physical review receipt for
the engine, effective brake, actual wheel direction, grade, and attendance.
"""
import json
from pathlib import Path

from instrument_producer import audit_stream, digest
from measure import SOURCES, measure, sha

REVIEW = ('engine_source_reviewed', 'wheel_calibration_reviewed',
          'attendance_source_reviewed', 'grade_perceptibility_reviewed',
          'brake_effectiveness_reviewed', 'wheel_direction_reviewed',
          'public_highway_and_purpose_reviewed')


def audit_attempt(folder, expected_case, review_path):
    folder = Path(folder)
    config = json.loads((folder / 'config.json').read_text())
    provenance = json.loads((folder / 'acquisition-provenance.json').read_text())
    if (config.get('case_id') != expected_case or
            config.get('selected_case_id') != expected_case):
        raise ValueError('Selected original case identity differs')
    if provenance.get('diagnostic_fixture') is not False or not provenance.get(
            'native_vehicle_actor_id'):
        raise ValueError('Original Native acquisition provenance missing')
    inventory = json.loads((folder / 'acquisition-hashes.json').read_text())
    if set(inventory) != set(SOURCES):
        raise ValueError('Complete original acquisition hash inventory missing')
    observations = measure(folder, inventory, diagnostic=False)
    packets = [json.loads(line) for line in
               (folder / 'instrument-frames.jsonl').read_text().splitlines()]
    source_audit = audit_stream(packets)
    retained_audit = json.loads((folder / 'instrument-audit.json').read_text())
    if retained_audit != source_audit:
        raise ValueError('Retained source audit differs from independent rerun')
    if source_audit['actor_id'] != provenance['native_vehicle_actor_id']:
        raise ValueError('Instrument source and Native actor differ')
    review = json.loads(Path(review_path).read_text())
    if (review.get('format') != 'c276263-physical-review-v1' or
            review.get('case_id') != expected_case or
            review.get('calibration_sha256') != source_audit['calibration_sha256'] or
            review.get('acquisition_hashes_sha256') != sha(folder / 'acquisition-hashes.json') or
            not isinstance(review.get('reviewer_id'), str) or not review['reviewer_id'] or
            any(review.get(key) is not True for key in REVIEW)):
        raise ValueError('Independent physical source and statutory-scope review incomplete')
    return {'format': 'c276263-independent-delivery-audit-v1',
            'case_id': expected_case, 'passed': True,
            'source_audit_sha256': digest(source_audit),
            'calibration_sha256': source_audit['calibration_sha256'],
            'review_sha256': sha(review_path),
            'measured_source_hashes': observations['source_hashes'],
            'statutory_observations': {
                'engine_running_any': observations['engine_running_any'],
                'parking_brake_unset_any': observations['parking_brake_unset_any'],
                'front_wheel_heading_to_curb_deg_range':
                    observations['front_wheel_heading_to_curb_deg_range']},
            'legal_verdict': None}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--review', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Use fresh independent audit output')
    output.write_text(json.dumps(audit_attempt(args.attempt, args.case,
                                               args.review), indent=2) + '\n')


if __name__ == '__main__':
    main()
