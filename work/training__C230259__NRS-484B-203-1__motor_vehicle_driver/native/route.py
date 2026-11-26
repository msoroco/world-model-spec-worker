"""Requested opposite-direction tracks; requested motion is never evidence."""

FRAMES = 600
RATE_HZ = 20
SETTINGS = {'witness_1': -2.0, 'witness_2': 1.0}


def requested_rows(case):
    if case not in SETTINGS:
        raise ValueError('Unknown exact meeting case')
    ego_y = SETTINGS[case]
    for frame in range(FRAMES):
        t = frame / RATE_HZ
        yield {'frame': frame, 'time_s': t,
               'ego_center_xyz_m': [round(-60 + 5 * t, 6), ego_y, 1.5],
               'oncoming_center_xyz_m': [round(60 - 5 * t, 6), 3.1, 1.5],
               'ego_heading_deg': 0, 'oncoming_heading_deg': 180,
               'requested_ego_lateral_center_y_m': ego_y,
               'road_id': 230259, 'ego_lane_id': -1, 'oncoming_lane_id': 1,
               'source_kind': 'synthetic_scene_request',
               'native_observed': False, 'legal_verdict': None}
