"""Deterministic proposed controller for 30-second Native pedestrian attempts."""
from construction import proposal


def command(suffix, frame):
    plan = proposal(suffix)
    if type(frame) is not int or not 0 <= frame < plan['frames']:
        raise ValueError('Controller frame outside 600-frame capture')
    move = plan['requested_walker_move_start_frame']
    permission = plan['requested_permission_start_frame']
    return {
        'frame': frame,
        'pedestrian_direction_xy': plan['requested_walker_direction_xy'],
        'pedestrian_speed_mps': plan['requested_walker_speed_mps'] if move is not None and frame >= move else 0.0,
        'requested_arrow_display': plan['requested_arrow_display'],
        'requested_other_device_permission': permission is not None and frame >= permission,
        'requested_only': True,
    }


def check():
    outputs = {suffix: [command(suffix, frame) for frame in range(600)]
               for suffix in ('probe_1', 'probe_2', 'permission_before_entry')}
    wait, early, permitted = (outputs[s] for s in
                              ('probe_1', 'probe_2', 'permission_before_entry'))
    if any(row['pedestrian_speed_mps'] != 0 for row in wait):
        raise ValueError('Wait controller moved pedestrian')
    if [row['pedestrian_speed_mps'] for row in early] != [
            row['pedestrian_speed_mps'] for row in permitted]:
        raise ValueError('Entry trajectories differ across permission comparison')
    if early[119]['pedestrian_speed_mps'] != 0 or early[120]['pedestrian_speed_mps'] <= 0:
        raise ValueError('Pedestrian entry start changed')
    if permitted[99]['requested_other_device_permission'] or not permitted[100]['requested_other_device_permission']:
        raise ValueError('Permission transition changed')
    if any(row['requested_other_device_permission'] for row in early):
        raise ValueError('Unpermitted entry requested permission')
    return {'frames_per_case': 600, 'rate_hz': 20, 'case_count': 3,
            'controller_checked': True, 'native_source_observed': False}
