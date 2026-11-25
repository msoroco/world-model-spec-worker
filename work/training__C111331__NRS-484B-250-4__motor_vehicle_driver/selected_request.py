"""Two 20 Hz controller requests against the repaired stop-line geometry."""
import argparse
import json
from pathlib import Path

FRAMES = 600


def row(frame, suffix, spawn_shift_m=0.0):
    if suffix not in ('controlled_1', 'controlled_2'):
        raise ValueError('Unknown exact case')
    if suffix == 'controlled_1':
        ego_x = -35 - spawn_shift_m + .05 * min(frame, 130) + .05 * max(0, frame - 220)
        phase = 'approach' if frame < 130 else 'hold_pre_line' if frame <= 220 else 'cautious_entry_request'
    else:
        ego_x = -35 - spawn_shift_m + .1 * frame
        phase = 'uninterrupted_entry_request'
    # The other vehicle completes an authored stop before the primary ego enters.
    other_y = -35 + .05 * min(frame, 130) + .05 * max(0, frame - 180)
    other_phase = 'approach' if frame < 130 else 'hold_pre_line' if frame <= 180 else 'entry_request'
    return {'frame': frame, 'time_s': frame / 20, 'source_kind': 'construction_request',
            'native_observed': False, 'ego_center_xy_m': [round(min(35, ego_x), 6), -1.75],
            'ego_front_x_m': round(min(35, ego_x) + 2, 6),
            'other_center_xy_m': [1.75, round(min(35, other_y), 6)],
            'ego_phase_requested': phase, 'other_phase_requested': other_phase,
            'marked_stop_line_x_m': -26.0, 'other_marked_stop_line_y_m': -26.0,
            'near_side_crosswalk_x_m': -23.0, 'intersection_entry_x_m': -20.0,
            'signal_state_requested': 'Off',
            'signal_id': 'c111331-installed-uncovered-vehicular-head',
            'signal_installed_requested': True, 'signal_uncovered_requested': True,
            'signal_display_requested': 'inoperative_dark', 'legal_verdict': None}


def build(suffix, spawn_shift_m=0.0):
    rows = [row(i, suffix, spawn_shift_m) for i in range(FRAMES)]
    if len(rows) != 600 or any(r['frame'] != i or r['time_s'] != i / 20
                               for i, r in enumerate(rows)):
        raise ValueError('Source request frame join differs')
    assert rows[130]['ego_center_xy_m'][0] + 2 < -26 if suffix == 'controlled_1' else True
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('controlled_1', 'controlled_2'), required=True)
    parser.add_argument('--spawn-shift-m', type=float, default=0.0)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    values = build(args.case, args.spawn_shift_m)
    Path(args.output).write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in values))
