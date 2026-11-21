"""Four genuinely different proposed construction settings per straight-yield case."""
from __future__ import annotations

BASE = 'training__C111088__NRS-484B-307-5a__motor_vehicle_driver'
CASES = {f'{BASE}__false': False, f'{BASE}__true': True}
KNOBS = {
    'primary': {'ego_spawn_y_m': -25.0, 'other_spawn_x_m': -14.0,
                'cross_traffic_target_m_s': 4.0, 'ego_target_m_s': 4.0,
                'clearance_margin_s': 0.40, 'overview_fov_deg': 90},
    'fallback1': {'ego_spawn_y_m': -28.0, 'other_spawn_x_m': -16.0,
                  'cross_traffic_target_m_s': 4.5, 'ego_target_m_s': 3.5,
                  'clearance_margin_s': 0.55, 'overview_fov_deg': 90},
    'fallback2': {'ego_spawn_y_m': -30.0, 'other_spawn_x_m': -12.0,
                  'cross_traffic_target_m_s': 3.5, 'ego_target_m_s': 4.5,
                  'clearance_margin_s': 0.70, 'overview_fov_deg': 95},
    'fallback3': {'ego_spawn_y_m': -32.0, 'other_spawn_x_m': -13.0,
                  'cross_traffic_target_m_s': 3.0, 'ego_target_m_s': 3.0,
                  'clearance_margin_s': 0.85, 'overview_fov_deg': 105},
}


def parameters(case_id: str, candidate_id: str) -> dict:
    if case_id not in CASES or candidate_id not in KNOBS:
        raise ValueError('Unknown exact case or candidate')
    return {'case_id': case_id, 'candidate_id': candidate_id,
            'lawful_conflict_participant_present': CASES[case_id],
            'rate_hz': 20, 'duration_s': 42,
            'knobs': dict(KNOBS[candidate_id]),
            'status': 'authored_native_proposal_unexecuted'}
