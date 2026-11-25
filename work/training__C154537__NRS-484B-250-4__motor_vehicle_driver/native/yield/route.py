"""Exact no-line same-cell requests for prior stop and intersection occupancy."""
FRAMES = 600
RATE_HZ = 20


def other_y(case, frame):
    if case == 'controlled_5':
        # Other vehicle fully stops before the crossing before ego's stop,
        # then clears before ego entry. Its requested history is the variable.
        if frame < 40:
            return -35 + frame * .2
        if frame < 60:
            return -27.0
        return min(35.0, -27 + (frame - 60) * .3)
    if case in ('controlled_6', 'controlled_7'):
        # Other vehicle pauses inside the junction during ego entry.
        if frame < 175:
            return -35 + frame * .2
        if frame < 260:
            return 0.0
        return min(35.0, (frame - 260) * .2)
    raise ValueError('Unknown yielding branch case')


def requested_rows(case):
    if case not in ('controlled_5', 'controlled_6', 'controlled_7'):
        raise ValueError('Unknown exact yielding case')
    for frame in range(FRAMES):
        release = 300 if case == 'controlled_7' else 220
        x = -35 + min(frame, 130) * .2 + max(0, frame - release) * .2
        x = min(x, 35)
        y = other_y(case, frame)
        yield {'frame': frame, 'time_s': frame / RATE_HZ,
               'ego_center_xy_m': [round(x, 6), -1.75],
               'ego_front_x_m': round(x + 2, 6),
               'other_center_xy_m': [1.75, round(y, 6)],
               'requested_signal_state': 'installed_uncovered_inoperative',
               'requested_stop_line_present': False,
               'requested_near_side_crosswalk_present': False,
               'requested_view_reference_center_x_m': -9.0,
               'intersection_entry_front_x_m': -6.0,
               'requested_yield_context': 'prior_completed_stop' if case == 'controlled_5'
                                          else 'other_within_intersection',
               'source_kind': 'synthetic_scene_request',
               'native_observed': False, 'legal_verdict': None}
