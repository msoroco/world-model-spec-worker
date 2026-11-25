"""Require independent original delivery acceptance on both comparison sides."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit as audit_delivery
from saved_comparison import audit_pair


def audit_comparison(comparison_id: str, left: dict, right: dict,
                     left_attempt: Path, right_attempt: Path,
                     left_processing: Path, right_processing: Path,
                     left_pixel_review: Path, right_pixel_review: Path,
                     *, delivery_check=audit_delivery, pair_check=audit_pair) -> dict:
    sides = (
        (left, left_attempt, left_processing, left_pixel_review),
        (right, right_attempt, right_processing, right_pixel_review),
    )
    accepted = []
    for manifest, attempt, processing, review in sides:
        case_id = manifest.get('case_id')
        if not case_id:
            raise ValueError('comparison side lacks exact case identity')
        for name, path in (('attempt', attempt), ('processing', processing),
                           ('pixel review', review)):
            if not Path(path).is_file() and name != 'attempt':
                raise ValueError(f'{case_id}: missing {name}')
            if name == 'attempt' and not Path(path).is_dir():
                raise ValueError(f'{case_id}: missing {name}')
        receipt = delivery_check(attempt, processing, review)
        if receipt.get('passed') is not True or receipt.get('case_id') != case_id or \
                receipt.get('source_integrity') is not True or \
                receipt.get('saved_only_processing') is not True or \
                receipt.get('actual_pixels_reviewed') is not True or \
                receipt.get('physical_case_completion') is not True or \
                receipt.get('all_participants') is not True or \
                receipt.get('time_join') is not True or \
                receipt.get('full_video_decode') is not True:
            raise ValueError(f'{case_id}: independent delivery audit incomplete')
        accepted.append(receipt)
    pair = pair_check(left, right, comparison_id,
                      attempt_roots=(Path(left_attempt), Path(right_attempt)))
    if pair.get('source_integrity') is not True or \
            pair.get('physical_case_completion') is not True:
        raise ValueError('comparison source or physical audit incomplete')
    return {'format': 'worker-freight-production-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': pair['case_ids'],
            'passed': True, 'independent_delivery_audits': accepted,
            'pair_measurement': pair, 'legal_conclusion': 'unresolved'}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    for side in ('left', 'right'):
        parser.add_argument('--' + side, required=True, type=Path)
        parser.add_argument('--' + side + '-attempt', required=True, type=Path)
        parser.add_argument('--' + side + '-processing', required=True, type=Path)
        parser.add_argument('--' + side + '-pixel-review', required=True, type=Path)
    args = parser.parse_args()
    left = json.loads(args.left.read_text())
    right = json.loads(args.right.read_text())
    result = audit_comparison(args.comparison, left, right,
                              args.left_attempt, args.right_attempt,
                              args.left_processing, args.right_processing,
                              args.left_pixel_review, args.right_pixel_review)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
