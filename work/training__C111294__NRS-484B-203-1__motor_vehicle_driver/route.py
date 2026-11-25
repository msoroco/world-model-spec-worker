"""Exact requested two-direction meeting tracks; original motion is measured later."""

FRAMES = 600
RATE_HZ = 20
SETTINGS = {'0.45': 0.45, '0.55': 0.55}


def requested_rows(case):
    if case not in SETTINGS:
        raise ValueError('Unknown exact meeting case')
    fraction = SETTINGS[case]
    ego_y = 1.0 - 2.0 * fraction
    for frame in range(FRAMES):
        t = frame / RATE_HZ
        yield {'frame': frame, 'time_s': t,
               'ego_center_xyz_m': [round(-60 + 5 * t, 6), round(ego_y, 6), 1.5],
               'oncoming_center_xyz_m': [round(60 - 5 * t, 6), 2.5, 1.5],
               'ego_heading_deg': 0, 'oncoming_heading_deg': 180,
               'requested_ego_right_half_body_fraction': fraction,
               'road_id': 111294, 'ego_lane_id': -1, 'oncoming_lane_id': 1,
               'source_kind': 'synthetic_scene_request',
               'native_observed': False, 'legal_verdict': None}
