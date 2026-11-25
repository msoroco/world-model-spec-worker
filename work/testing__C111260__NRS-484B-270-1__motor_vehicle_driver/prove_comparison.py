"""Re-audit both three-frame diagnostic Originals before an exact comparison."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile

import comparison_audit
from delivery_audit import audit as delivery_audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rider-kind', required=True)
    parser.add_argument('--left-attempt', type=Path, required=True)
    parser.add_argument('--right-attempt', type=Path, required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    args = parser.parse_args()
    comparison_audit.audit_delivery = lambda attempt, case, review: delivery_audit(
        attempt, case, review, expected_frames=3, diagnostic_fixture=True)
    left_review = args.left_attempt / 'pixel-review.json'
    if args.mode == 'negative':
        with tempfile.TemporaryDirectory(dir=args.right_attempt.parent) as temporary:
            right = Path(temporary) / 'right'
            shutil.copytree(args.right_attempt, right)
            right_review = right / 'pixel-review.json'
            review = json.loads(right_review.read_text())
            review['views']['reference_corner']['framemd5_sha256'] = '0' * 64
            right_review.write_text(json.dumps(review, indent=2) + '\n')
            result = comparison_audit.audit_saved(args.left_attempt, right,
                                                  left_review, right_review, args.rider_kind)
    else:
        right_review = args.right_attempt / 'pixel-review.json'
        result = comparison_audit.audit_saved(args.left_attempt, args.right_attempt,
                                              left_review, right_review, args.rider_kind)
    print(json.dumps({'scope': 'three-frame synthetic diagnostic only',
                      'result': result}, indent=2))


if __name__ == '__main__':
    main()
