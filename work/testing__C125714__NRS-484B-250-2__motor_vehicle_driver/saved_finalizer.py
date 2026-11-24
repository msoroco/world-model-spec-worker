"""Selected-requirement diagnostic from sealed original C125714 sources.

This finalizer records measured entry timing and source identity. It does not
decide what `approximately the same time` or legal yielding means.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

MODULE = Path(__file__).with_name('entry_timing.py')
SPEC = importlib.util.spec_from_file_location('c125714_entry_measure', MODULE)
entry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(entry)
ASSIGNMENT = entry.ASSIGNMENT
ALLOWED = {ASSIGNMENT + '__' + suffix for suffix in (
    'timing_below_training', 'timing_inside_training', 'timing_above_training')}


def finalize(attempt: Path, case_id: str, diagnostic_fixture: bool = False) -> dict:
    if case_id not in ALLOWED:
        raise ValueError('selected exact case is not in executable coverage')
    measured = entry.measure(Path(attempt), diagnostic_fixture=diagnostic_fixture)
    if measured.get('case_id') != case_id:
        raise ValueError('saved original case identity differs from selected case')
    if measured['approach_relation'] != 'crossing' or measured['ego_side'] != 'left' or \
            measured['other_side'] != 'right' or \
            measured['official_device_controls_intersection'] is not False or \
            measured['other_left_turn_intent'] is not False or \
            measured['subsection_4_context_reviewed'] is not True:
        raise ValueError('selected left-yields-right crossing context not source established')
    return {'format': 'worker-c125714-selected-diagnostic-v1',
            'assignment_id': ASSIGNMENT, 'case_id': case_id,
            'selected_requirement': 'NRS-484B-250-2 left yields to right at different-highway intersection',
            'measurement': 'intersection_entry_time_difference_s',
            'measured_value_s': measured['intersection_entry_time_difference_s'],
            'difference_bracket_s': measured['difference_bracket_s'],
            'ego_entry': measured['ego_entry'], 'other_entry': measured['other_entry'],
            'crossing_id': measured['crossing_id'],
            'roadway_id': measured['roadway_id'],
            'ego_side': measured['ego_side'], 'other_side': measured['other_side'],
            'approach_relation': measured['approach_relation'],
            'official_device_controls_intersection': measured['official_device_controls_intersection'],
            'other_left_turn_intent': measured['other_left_turn_intent'],
            'subsection_4_context_reviewed': measured['subsection_4_context_reviewed'],
            'original_frame_count': measured['original_frame_count'],
            'source_sha256': measured['source_sha256'],
            'approximately_same_time': 'unresolved_judgment',
            'right_of_way_yielding': 'unresolved_original_behavior_review',
            'legal_verdict_claimed': False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = finalize(args.attempt, args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n',
                           encoding='utf-8')


if __name__ == '__main__':
    main()
