"""Independent saved-source audit for the two exact diagonal comparisons."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit_delivery
from saved_crossing import ASSIGNMENT, audit_saved_comparison, process_saved


PAIRS = {
    'diagonal_instruction_permissive_vs_prohibitive':
        (ASSIGNMENT + '__permissive_whole_crossing',
         ASSIGNMENT + '__prohibitive_whole_crossing'),
    'diagonal_instruction_phase_change':
        (ASSIGNMENT + '__permissive_whole_crossing',
         ASSIGNMENT + '__instruction_changes_during_crossing'),
}


def audit_attempt_pair(comparison_id, reference_attempt, variant_attempt,
                       *, reference_review_ref=None, variant_review_ref=None,
                       allow_diagnostic=False):
    if comparison_id not in PAIRS:
        raise ValueError('undeclared diagonal comparison')
    left_case, right_case = PAIRS[comparison_id]
    left_root = Path(reference_attempt).resolve()
    right_root = Path(variant_attempt).resolve()
    if left_root == right_root:
        raise ValueError('comparison requires two original attempts')
    left = process_saved(left_root, left_case, left_root / 'comparison-left-measurement.json',
                         allow_diagnostic=allow_diagnostic)
    right = process_saved(right_root, right_case, right_root / 'comparison-right-measurement.json',
                          allow_diagnostic=allow_diagnostic)
    if left['original_frames'] != 900 or right['original_frames'] != 900:
        raise ValueError('comparison requires both complete original 900-frame crossings')
    if not allow_diagnostic:
        if not left['full_video_decode'] or not right['full_video_decode']:
            raise ValueError('comparison original four-camera decodes missing')
        audit_delivery(left_root, left_case, physical_review_ref=reference_review_ref)
        audit_delivery(right_root, right_case, physical_review_ref=variant_review_ref)
    controlled = audit_saved_comparison(left, right, allow_diagnostic=allow_diagnostic)
    return {'format': 'worker-comparison-audit', 'comparison_id': comparison_id,
            'case_ids': [left_case, right_case],
            'diagnostic': allow_diagnostic,
            'fixed_conditions_checked': ['site SHA256', 'governing device and source hashes',
                                         'exception review state', '20 Hz four cameras',
                                         'crossing original frames'],
            'deliberate_difference': 'observed diagonal pedestrian instruction',
            'comparison_verified': controlled['comparison_verified'],
            'physical_realization': 'unconfirmed' if allow_diagnostic else 'independently_reviewed',
            'legal_conclusion': 'not_assessed'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison-id', required=True)
    parser.add_argument('--reference-attempt', required=True)
    parser.add_argument('--variant-attempt', required=True)
    parser.add_argument('--reference-review-ref', required=True)
    parser.add_argument('--variant-review-ref', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    left_ref = json.loads(Path(args.reference_review_ref).read_text())
    right_ref = json.loads(Path(args.variant_review_ref).read_text())
    result = audit_attempt_pair(args.comparison_id, args.reference_attempt,
                                args.variant_attempt, reference_review_ref=left_ref,
                                variant_review_ref=right_ref)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
