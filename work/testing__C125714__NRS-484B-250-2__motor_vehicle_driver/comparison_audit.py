"""Independent saved-diagnostic comparison of exact training probes.

Only original sealed case diagnostics are eligible. The audit checks isolation
and observed timing order; it never labels a legal approximately-same-time band.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

BASE = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver'
ORDER = tuple(BASE + '__timing_' + name + '_training' for name in
              ('below', 'inside', 'above'))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(diagnostics: list[dict]) -> dict:
    require(len(diagnostics) == 3 and
            tuple(d.get('case_id') for d in diagnostics) == ORDER,
            'three ordered exact timing diagnostics required')
    require(all(d.get('format') == 'worker-c125714-selected-diagnostic-v1' and
                d.get('assignment_id') == BASE and d.get('source_sha256') and
                d.get('measurement') == 'intersection_entry_time_difference_s' and
                d.get('legal_verdict_claimed') is False for d in diagnostics),
            'source-bound original selected diagnostics required')
    fixed = ('crossing_id', 'roadway_id', 'ego_side', 'other_side',
             'approach_relation', 'official_device_controls_intersection',
             'other_left_turn_intent', 'subsection_4_context_reviewed',
             'original_frame_count')
    for key in fixed:
        require(all(d.get(key) == diagnostics[0].get(key) for d in diagnostics) and
                diagnostics[0].get(key) is not None,
                'fixed comparison condition changed: ' + key)
    # Case IDs make site-context bytes distinct; compare its reviewed fields above.
    # The physical map bytes must match exactly across all three cases.
    for source in ('road.xodr',):
        require(all(d['source_sha256'].get(source) ==
                    diagnostics[0]['source_sha256'].get(source)
                    for d in diagnostics) and
                diagnostics[0]['source_sha256'].get(source),
                'fixed original source changed: ' + source)
    values = [d.get('measured_value_s') for d in diagnostics]
    require(all(type(x) in (int, float) and math.isfinite(x) for x in values) and
            values[0] < values[1] < values[2],
            'ordered actual timing difference not measured')
    return {'format': 'worker-c125714-independent-comparison-v1',
            'case_ids': list(ORDER), 'measured_entry_differences_s': values,
            'fixed_source_sha256': {'road.xodr': diagnostics[0]['source_sha256']['road.xodr']},
            'legal_verdict_claimed': False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--diagnostic', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit([json.loads(path.read_text(encoding='utf-8'))
                    for path in args.diagnostic])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n',
                           encoding='utf-8')


if __name__ == '__main__':
    main()
