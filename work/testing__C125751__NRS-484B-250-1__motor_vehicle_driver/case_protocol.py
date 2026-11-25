"""Exact-case planning protocol for the C125751 signal-controlled crossing.

These are requested capture conditions. The original-frame saved audit decides
what happened; no authored value is used as a measured or legal outcome.
"""
from __future__ import annotations

import json
from pathlib import Path


ASSIGNMENT = 'testing__C125751__NRS-484B-250-1__motor_vehicle_driver'
SUFFIXES = ('precedence', 'advance', 'other_later', 'signal_red')
FIXED = ('law_id', 'cell_id', 'actor', 'layout', 'maneuver', 'control',
         'source_packet_sha256', 'map_sha256', 'crossing_id',
         'ego_route_sha256', 'other_route_sha256', 'camera_plan_sha256',
         'duration_frames', 'ego_blueprint', 'other_blueprint')
EXPECTED = {
    'precedence': (True, 'Green', 'yield'),
    'advance': (True, 'Green', 'advance'),
    'other_later': (False, 'Green', 'yield'),
    'signal_red': (True, 'Red', 'yield'),
}
COMPARISONS = {
    'median_entry_order': ('precedence', 'other_later', 'other_first'),
    'official_signal_readback': ('precedence', 'signal_red', 'ego_light_request'),
}


def load_case(folder: Path, suffix: str) -> dict:
    if suffix not in SUFFIXES:
        raise ValueError('undefined exact case')
    return json.loads((folder / 'cases' / suffix / 'case-spec.json').read_text())


def validate_case(spec: dict, suffix: str):
    if suffix not in SUFFIXES or spec.get('case_id') != ASSIGNMENT + '__' + suffix:
        raise ValueError('exact case identity differs')
    for key, expected in (('law_id', 'NRS-484B-250-1'), ('cell_id', 'C125751'),
                          ('actor', 'motor_vehicle_driver'), ('layout', 'median_opening'),
                          ('maneuver', 'travel'), ('control', 'traffic_light')):
        if spec.get(key) != expected:
            raise ValueError('fixed cell identity differs: ' + key)
    if (spec.get('other_first'), spec.get('ego_light_request'),
            spec.get('ego_response_request')) != EXPECTED[suffix]:
        raise ValueError('case request differs from declared variant')
    if spec.get('source_status') != 'original_review_required':
        raise ValueError('source review boundary absent')
    for key in FIXED[6:]:
        if not spec.get(key):
            raise ValueError('source or capture binding absent: ' + key)
    if spec.get('rate_hz') != 20 or spec.get('duration_frames') != 1100:
        raise ValueError('shared 20 Hz capture contract differs')
    return spec


def validate_comparison(left: dict, right: dict, comparison_id: str):
    if comparison_id not in COMPARISONS:
        raise ValueError('undefined comparison')
    a, b, variable = COMPARISONS[comparison_id]
    validate_case(left, a)
    validate_case(right, b)
    for key in FIXED:
        if left[key] != right[key]:
            raise ValueError('fixed condition changed: ' + key)
    changed = {key for key in ('other_first', 'ego_light_request')
               if left[key] != right[key]}
    if changed != {variable}:
        raise ValueError('comparison variable not isolated')
    return {'comparison_id': comparison_id,
            'case_ids': [left['case_id'], right['case_id']],
            'changed_request': variable,
            'measured_outcome_pending': True}
