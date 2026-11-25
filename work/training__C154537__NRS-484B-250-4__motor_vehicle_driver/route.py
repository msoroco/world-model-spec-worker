"""Controlled 30-second requested tracks for the final stopping-location fallback."""
FRAMES = 600
RATE_HZ = 20


def requested_rows(case):
    if case not in ('controlled_1', 'controlled_2'):
        raise ValueError('Unknown exact case')
    for frame in range(FRAMES):
        if case == 'controlled_1':
            # The plateau requests a halt before entry; actual Native cessation is measured later.
            x = -35 + min(frame, 130) * .2 + max(0, frame - 220) * .2
        else:
            x = -35 + frame * .2
        x = min(x, 35)
        other_y = min(35, -35 + frame * .2)
        yield {'frame': frame, 'time_s': frame / RATE_HZ,
               'ego_center_xy_m': [round(x, 6), -1.75],
               'ego_front_x_m': round(x + 2, 6),
               'other_center_xy_m': [1.75, round(other_y, 6)],
               'requested_signal_state': 'installed_uncovered_inoperative',
               'requested_stop_line_present': False,
               'requested_near_side_crosswalk_present': False,
               'requested_view_reference_center_x_m': -9.0,
               'intersection_entry_front_x_m': -6.0,
               'source_kind': 'synthetic_scene_request',
               'native_observed': False, 'legal_verdict': None}
