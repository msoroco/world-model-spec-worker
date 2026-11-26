"""Classify exact-case recorded motion evidence without legal inference."""
from __future__ import annotations

from math import hypot, isfinite
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
        positions = [row.get('ego_position_m') for row in rows]
        positions_valid = all(isinstance(pos, list) and len(pos) == 3 and
                              all(type(value) in (int, float) and isfinite(value) for value in pos)
                              for pos in positions)
        body_centers = [(row['body_west_x_m'] + row['body_east_x_m']) / 2 for row in rows]
        position_motion = (sum(hypot(positions[i][0] - positions[i-1][0],
                                     positions[i][1] - positions[i-1][1])
                               for i in range(1, len(positions))) if positions_valid else 0.0)
        body_displacement = abs(body_centers[-1] - body_centers[0])
        approach_observed = (position_motion > 0.25 and body_displacement > 0.25 and
                             any(row['ego_speed_mps'] > 0.1 and
                                 row['activity_observation'] == 'moving' for row in rows[:-20]))
        hold = measured['original_measurements'][-20:]
        target_region = 'front_overlap' if case.region == 'front' else case.region
        target_gap = 0.0 if case.region == 'front' else case.gap_m
        hold_met = all(item['region'] == target_region and
                       abs(item['side_gap_m'] - target_gap) <= 0.15 and
                       item['activity_observation'] == activity and item['speed_mps'] <= 0.2
                       for item in hold)
        met = approach_observed and hold_met
        status = 'unverified' if not positions_valid else ('met' if met else 'not_met')
        realized = {'observed_regions': measured['observed_regions'],
                    'observed_activities': measured['observed_activities'],
                    'min_side_gap_m': measured['min_side_gap_m'],
                    'final_hold_side_gap_m': min(item['side_gap_m'] for item in hold),
                    'front_overlap_frames': measured['front_overlap_frames'],
                    'observed_position_path_m': position_motion,
                    'body_center_displacement_m': body_displacement,
                    'final_target_hold_samples': len(hold) if hold_met else 0}
    return {'case_id': case.id, 'physical_checks': {
                'maneuver': {'status': status,
                             'method': 'original 900-frame approach motion and 20-sample target hold with exact case geometry',
                             'sources': sources}},
            'maneuver_completed': status == 'met',
            'realized_observables': realized if status == 'met' else None,
            'provenance_kind': 'synthetic_fixture' if diagnostic_fixture else 'original_native',
            'diagnostic_fixture': diagnostic_fixture,
            'fixture_visibility_verified': False,
            'legal_judgment': None}
