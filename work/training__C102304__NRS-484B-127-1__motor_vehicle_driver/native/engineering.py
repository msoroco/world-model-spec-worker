"""Unselected Native engineering policies and source-bound fallback triggers."""
import math

from geometry import GAP_TARGET_M, RATE_HZ

CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def parameters(case_suffix, candidate):
    if case_suffix not in GAP_TARGET_M or candidate not in CANDIDATES:
        raise ValueError('Unknown C102304 case or candidate')
    config = {'case_suffix': case_suffix, 'candidate_id': candidate,
              'cell_id': 'C102304', 'law_id': 'NRS-484B-127-1',
              'actor': 'motor_vehicle_driver', 'road_id': 1, 'lane_id': -1,
              'rate_hz': RATE_HZ, 'duration_s': 45,
              'target_bumper_gap_m': GAP_TARGET_M[case_suffix],
              'ego_start_x_m': -80.0, 'lead_start_policy': 'moving_same_lane',
              'ego_target_speed_mps': 8.0, 'lead_target_speed_mps': 8.0,
              'controller_lookahead_m': 8.0,
              'camera_horizontal_fov_deg': 90.0,
              'camera_mount_height_m': 1.65,
              'construction_status': 'unselected_proposal'}
    if candidate == 'fallback1':
        config['ego_start_x_m'] = -95.0
        config['lead_start_policy'] = 'moving_same_lane_with_15m_approach_extension'
    elif candidate == 'fallback2':
        config['controller_lookahead_m'] = 5.0
    elif candidate == 'fallback3':
        config['camera_horizontal_fov_deg'] = 110.0
        config['camera_mount_height_m'] = 2.0
    return config


TRIGGERS = {
    'fallback1': {'source': 'original Native actor spawn and full-body samples',
                  'metric': 'minimum_spawn_body_clearance_m', 'threshold': 2.0},
    'fallback2': {'source': 'original Native body and route samples',
                  'metric': 'maximum_gap_tracking_error_m', 'threshold': 2.0},
    'fallback3': {'source': 'independent original-pixel lead-body visibility audit',
                  'metric': 'lead_body_visible_fraction', 'threshold': .95},
}


def trigger(candidate, evidence):
    if candidate not in TRIGGERS or not isinstance(evidence, dict):
        raise ValueError('Unknown fallback or evidence')
    specification = TRIGGERS[candidate]
    if evidence.get('source') != specification['source']:
        raise ValueError('Original measurement source missing')
    value = evidence.get(specification['metric'])
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid measured trigger')
    if candidate == 'fallback3':
        if value > 1:
            raise ValueError('Visibility fraction outside [0,1]')
        return value < specification['threshold']
    if candidate == 'fallback1':
        return value < specification['threshold']
    return value > specification['threshold']


def ego_velocity_request(plan, observed_bumper_gap_m):
    """Bounded gap tracking request; actual Native speed remains an observation."""
    if type(observed_bumper_gap_m) not in (int, float) or not math.isfinite(observed_bumper_gap_m):
        raise ValueError('Observed Native bumper gap missing')
    if observed_bumper_gap_m <= 0:
        raise ValueError('Actual Native bodies have no positive following gap')
    correction = 2*(observed_bumper_gap_m-plan['target_bumper_gap_m'])/plan['controller_lookahead_m']
    return max(6.0, min(10.0, plan['ego_target_speed_mps']+correction))
