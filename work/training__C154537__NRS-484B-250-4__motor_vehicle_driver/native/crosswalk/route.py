"""Exact requested stop at a marked line on the same one-way junction."""
FRAMES = 600
RATE_HZ = 20


def requested_rows(case):
    if case != 'controlled_4':
        raise ValueError('Unknown exact line case')
    for frame in range(FRAMES):
        # Center -11 places the requested front at the crosswalk near edge x=-10.
        x = -35 + min(frame, 115) * .2 + max(0, frame - 215) * .2
        x = min(x, 35)
        other_y = min(35, -35 + frame * .2)
        yield {'frame': frame, 'time_s': frame / RATE_HZ,
               'ego_center_xy_m': [round(x, 6), -1.75],
               'ego_front_x_m': round(x + 2, 6),
               'other_center_xy_m': [1.75, round(other_y, 6)],
               'requested_signal_state': 'installed_uncovered_inoperative',
               'requested_stop_line_present': False,
               'requested_near_side_crosswalk_present': True,
               'requested_crosswalk_near_edge_x_m': -10.0,
               'intersection_entry_front_x_m': -6.0,
               'source_kind': 'synthetic_scene_request',
               'native_observed': False, 'legal_verdict': None}
