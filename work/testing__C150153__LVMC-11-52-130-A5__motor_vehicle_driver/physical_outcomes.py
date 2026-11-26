"""Classify exact-case recorded motion evidence without legal inference."""
from __future__ import annotations

from math import isfinite
from typing import Mapping

from parking import CASES, measure_original_history


LIFECYCLE = ["capture_finished", "encoders_closed", "restoration_verified",
             "native_exit", "owner_released", "saved_processing_started"]


def verify_lifecycle(events: list[str]) -> bool:
    if events != LIFECYCLE:
        raise ValueError("saved processing precedes Native ownership closure")
    return True


def evaluate(case, rows: list[Mapping] | None, site: Mapping,
             history_sha256: str | None, site_packet_sha256: str,
             *, diagnostic_fixture: bool = False) -> dict:
    if case not in CASES:
        raise ValueError("unknown exact sidewalk-elevator case")
    sources = {'site_packet_sha256': site_packet_sha256}
    if history_sha256:
        sources['original_history_sha256'] = history_sha256
    measured = None
    if rows and history_sha256 and len(rows) == 900:
        try:
            measured = measure_original_history(rows, site, case)
        except (ValueError, KeyError, TypeError):
            measured = None
    if measured is None:
        status = 'unverified'
        realized = {}
    else:
        activity = {'stop': 'stopped', 'stand': 'standing', 'park': 'parked'}[case.activity]
        if case.region == 'front':
            region_met = measured['front_overlap_frames'] > 0
            target_gap = 0.0
        else:
            region_met = case.region in measured['observed_regions']
            target_gap = case.gap_m
        gap = measured['min_side_gap_m']
        gap_met = type(gap) in (int, float) and isfinite(gap) and abs(gap - target_gap) <= 0.15
        met = region_met and gap_met and activity in measured['observed_activities']
        status = 'met' if met else 'not_met'
        realized = {'observed_regions': measured['observed_regions'],
                    'observed_activities': measured['observed_activities'],
                    'min_side_gap_m': gap,
                    'front_overlap_frames': measured['front_overlap_frames']}
    return {'case_id': case.id, 'physical_checks': {
                'maneuver': {'status': status,
                             'method': 'measure_original_history and exact case target geometry',
                             'sources': sources}},
            'maneuver_completed': status == 'met',
            'realized_observables': realized if status == 'met' else None,
            'provenance_kind': 'synthetic_fixture' if diagnostic_fixture else 'original_native',
            'diagnostic_fixture': diagnostic_fixture,
            'fixture_visibility_verified': False,
            'legal_judgment': None}
