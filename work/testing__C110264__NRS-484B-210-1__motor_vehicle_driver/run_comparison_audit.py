"""Compare independently reopened source audits for one exact case pair."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pass_right_audit import audit_comparison
from prove_delivery_audit import audit


ASSIGNMENT = 'testing__C110264__NRS-484B-210-1__motor_vehicle_driver'
PAIRS = {'left_signal_presence': ('left_signal', 'neither'),
         'left_turn_motion_presence': ('left_turn', 'neither')}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison-id', choices=tuple(PAIRS), required=True)
    parser.add_argument('--attempt-a', type=Path, required=True)
    parser.add_argument('--attempt-b', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    left, right = PAIRS[args.comparison_id]
    a = audit(args.attempt_a / 'original-attempt', ASSIGNMENT + '__' + left)
    b = audit(args.attempt_b / 'original-attempt', ASSIGNMENT + '__' + right)
    result = audit_comparison(a, b, args.comparison_id)
    result['source_scope'] = 'synthetic diagnostic comparison only'
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
