"""Production CLI for two sealed original C111329 crossing attempts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import audit_saved_pair
from original_attempt_audit import audit as audit_original
from saved_process import ASSIGNMENT

PAIRS = {
    'diagonal_path_without_authority': ('adjacent_no_diagonal_authority', 'diagonal_no_authority'),
    'diagonal_device_authority': ('diagonal_no_authority', 'diagonal_authorized'),
    'authorized_device_path_control': ('diagonal_authorized', 'adjacent_authorized_device'),
}


def audit(comparison: str, first_attempt: Path, first_refs: list[dict],
          second_attempt: Path, second_refs: list[dict], *,
          allow_diagnostic: bool = False, expected_frames: int = 900) -> dict:
    if comparison not in PAIRS:
        raise ValueError('unknown exact C111329 comparison')
    if not allow_diagnostic and expected_frames != 900:
        raise ValueError('production comparison requires 900 original frames')
    case_ids = [ASSIGNMENT + '__' + suffix for suffix in PAIRS[comparison]]
    originals = [audit_original(first_attempt, case_ids[0], first_refs,
                               allow_diagnostic=allow_diagnostic,
                               expected_frames=expected_frames),
                 audit_original(second_attempt, case_ids[1], second_refs,
                               allow_diagnostic=allow_diagnostic,
                               expected_frames=expected_frames)]
    pair = audit_saved_pair(first_attempt, first_refs, second_attempt, second_refs,
                            comparison, allow_diagnostic=allow_diagnostic,
                            expected_frames=expected_frames)
    if pair['case_ids'] != case_ids or any(row['case_id'] != case for row, case in zip(originals, case_ids)):
        raise ValueError('original comparison case order mismatch')
    if any(row['exception_484B_290'] != 'unresolved' or row['legal_verdict'] is not None
           for row in originals):
        raise ValueError('unsupported legal practicability conclusion')
    return {**pair, 'format': 'c111329-original-comparison-audit-v1',
            'original_attempt_audit_sha256': [hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
                                              for row in originals],
            'source_join_count': expected_frames,
            'production': not allow_diagnostic}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True, choices=sorted(PAIRS))
    parser.add_argument('--first-attempt', type=Path, required=True)
    parser.add_argument('--first-refs', type=Path, required=True)
    parser.add_argument('--second-attempt', type=Path, required=True)
    parser.add_argument('--second-refs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    parser.add_argument('--expected-frames', type=int, default=900)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('original comparison output already exists')
    first = json.loads(args.first_refs.read_text(encoding='utf-8'))
    second = json.loads(args.second_refs.read_text(encoding='utf-8'))
    result = audit(args.comparison, args.first_attempt, first,
                   args.second_attempt, second,
                   allow_diagnostic=args.allow_diagnostic,
                   expected_frames=args.expected_frames)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'comparison_id': result['comparison_id'], 'case_ids': result['case_ids'],
                      'source_join_count': result['source_join_count'],
                      'production': result['production']}, sort_keys=True))


if __name__ == '__main__':
    main()
