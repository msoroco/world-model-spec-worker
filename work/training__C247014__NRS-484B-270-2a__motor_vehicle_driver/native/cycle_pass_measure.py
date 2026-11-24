"""Saved-source diagnostic for immediate-left-lane cycle passing."""
import json
import math
from pathlib import Path

FRAME_COUNT = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
MACHINES = ('bicycle', 'electric_bicycle', 'electric_scooter')


def derive(folder):
    folder = Path(folder)
    setup = json.loads((folder / 'setup.json').read_text())
    frames = json.loads((folder / 'raw-frames.json').read_text())
    if setup.get('source_kind') != 'synthetic_native_sample':
        raise ValueError('Source kind missing')
    if setup.get('cycle_kind') not in MACHINES:
        raise ValueError('Covered cycle source missing')
    lane_count = setup.get('same_direction_lane_count')
    if not isinstance(lane_count, int) or lane_count < 2:
        raise ValueError('Multiple same-direction lanes source missing')
    if setup.get('right_lane_id') == setup.get('immediate_left_lane_id'):
        raise ValueError('Distinct immediate-left lane source missing')
    if not isinstance(setup.get('left_lane_available'), bool):
        raise ValueError('Left-lane availability source missing')
    if not isinstance(setup.get('left_move_reasonably_safe'), bool):
        raise ValueError('Left-move safety source missing')
    if len(frames) != FRAME_COUNT:
        raise ValueError('Incomplete same-direction pass history')
    abreast = []
    left = []
    first_left = None
    for i, frame in enumerate(frames):
        if frame.get('frame') != i or abs(frame.get('elapsed_s', -1) - i / 20) > 1e-9:
            raise ValueError('Frame/time join failed')
        if tuple(frame.get('camera_ids', ())) != CAMERAS:
            raise ValueError('Four source camera identities missing')
        x, cycle_x = frame.get('ego_x_m'), frame.get('cycle_x_m')
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, cycle_x)):
            raise ValueError('Vehicle/cycle longitudinal pose missing')
        if frame.get('ego_heading') != '+x' or frame.get('cycle_heading') != '+x':
            raise ValueError('Same-direction source missing')
        lane = frame.get('ego_lane_id')
        if lane not in (setup['right_lane_id'], setup['immediate_left_lane_id']):
            raise ValueError('Measured lane identity missing')
        if lane == setup['immediate_left_lane_id']:
            left.append(i)
            if first_left is None:
                first_left = i
        # Longitudinal four-metre body overlap defines the sampled passing span.
        if abs(x - cycle_x) <= 4:
            abreast.append(i)
    if not abreast:
        raise ValueError('No measured cycle pass')
    return {'source_kind': setup['source_kind'], 'cycle_kind': setup['cycle_kind'],
            'pass_first_frame': abreast[0], 'pass_last_frame': abreast[-1],
            'pass_frames': len(abreast),
            'ego_immediate_left_lane_during_pass_frames': sum(i in left for i in abreast),
            'first_immediate_left_lane_frame': first_left,
            'left_lane_available_declaration': setup['left_lane_available'],
            'left_move_reasonably_safe_declaration': setup['left_move_reasonably_safe'],
            'availability_and_safety_verified': False,
            'due_care_judged': False, 'native_motion_proven': False,
            'legal_conclusion': None}
