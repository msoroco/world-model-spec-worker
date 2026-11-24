"""Independent saved-only comparison of three exact speed attempts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis import finalize
from speed_boundary import compare


def audit(plan: Path, attempts: dict[str, Path], *,
          allow_diagnostic: bool = False) -> dict:
    result = compare(plan, attempts)
    if result['diagnostic_fixture'] and not allow_diagnostic:
        raise ValueError('diagnostic fixture cannot enter delivery comparison')
    measurements = {}
    for case_id, attempt in attempts.items():
        selected = finalize(attempt, case_id,
                            allow_diagnostic=allow_diagnostic)
        measurements[case_id] = {
            'selected_measurements': selected['measurements'],
            'full_video_decode': selected['full_video_decode'],
            'capture_index_sha256': hashlib.sha256(
                (Path(attempt) / 'capture-index.json').read_bytes()).hexdigest(),
        }
    return {'format': 'c10301-saved-comparison-audit-v1',
            'comparison': result, 'case_measurements': measurements,
            'physical_acceptance_claimed': False,
            'legal_judgment': 'unresolved'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    for suffix in ('below', 'equal', 'above'):
        parser.add_argument('--' + suffix, type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    prefix = 'testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__'
    attempts = {prefix + suffix: getattr(args, suffix)
                for suffix in ('below', 'equal', 'above')}
    result = audit(args.plan, attempts,
                   allow_diagnostic=args.allow_diagnostic)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
