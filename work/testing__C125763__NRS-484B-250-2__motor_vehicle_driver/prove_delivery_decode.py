"""Reproduce all four independent CPU camera-decode and missing-source checks."""
import json
import shutil
import tempfile
from pathlib import Path

from audit_delivery import audit
from runner import ASSIGNMENT

REPO = Path(__file__).resolve().parents[2]
CASES = (
    ('primary', 'yield_ego_left_near_time'),
    ('right', 'yield_ego_right_near_time'),
    ('separated', 'yield_ego_left_separated'),
    ('opposite', 'yield_opposite_left_turn'),
)


def main():
    for prefix, suffix in CASES:
        case_id = ASSIGNMENT + '__' + suffix
        attempt = REPO / '.runtime-work' / ('c125763-canonical-' + prefix + '-compat-v1')
        receipt = audit(attempt, 'analysis-report.json', decode=True, expected_case=case_id)
        if (not receipt['full_video_decode_passed'] or
                set(receipt['decoded_cameras']) != {
                    'overview', 'approach', 'reference_corner', 'driver_reference'} or
                receipt['delivery_ready'] or receipt['physical_acceptance_claimed']):
            raise ValueError('Incorrect CPU decode outcome: ' + case_id)
        with tempfile.TemporaryDirectory(prefix='c125763-delivery-negative-') as tmp:
            broken = Path(tmp) / 'attempt'
            shutil.copytree(attempt, broken)
            (broken / 'approach.mkv').unlink()
            try:
                audit(broken, 'analysis-report.json', decode=True, expected_case=case_id)
            except ValueError as error:
                if str(error) != 'Missing original/delivered source: approach.mkv':
                    raise
                negative = str(error)
            else:
                raise ValueError('Missing original camera was accepted: ' + case_id)
        print(json.dumps({'case_id': case_id, 'positive': 'four-camera full decode passed',
                          'negative': negative, 'diagnostic_only': True,
                          'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
