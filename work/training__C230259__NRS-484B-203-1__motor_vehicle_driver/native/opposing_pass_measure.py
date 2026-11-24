"""Saved body geometry diagnostic for NRS 484B.203(1), no legal cutoff."""
import json
import math
from pathlib import Path

FRAME_COUNT = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def derive(folder):
    folder = Path(folder)
    setup = json.loads((folder / 'setup.json').read_text())
    frames = json.loads((folder / 'raw-frames.json').read_text())
    if setup.get('source_kind') != 'synthetic_native_sample':
        raise ValueError('Source kind missing')
    if setup.get('traffic_lines_each_direction') != 1:
        raise ValueError('Road width/traffic-line source missing')
    paved = setup.get('paved_y_bounds_m')
    if (not isinstance(paved, list) or len(paved) != 2 or
            not all(isinstance(v, (int, float)) and math.isfinite(v) for v in paved)
            or paved[0] >= 0 or paved[1] <= 0):
        raise ValueError('Paved portion/center source missing')
    half_width = setup.get('vehicle_half_width_m')
    if not isinstance(half_width, (int, float)) or not math.isfinite(half_width) or half_width <= 0:
        raise ValueError('Vehicle body width source missing')
    if len(frames) != FRAME_COUNT:
        raise ValueError('Incomplete opposing approach history')
    meeting = []
    ego_left_half = []
    other_left_half = []
    for i, frame in enumerate(frames):
        if frame.get('frame') != i or abs(frame.get('elapsed_s', -1) - i / 20) > 1e-9:
            raise ValueError('Frame/time join failed')
        if tuple(frame.get('camera_ids', ())) != CAMERAS:
            raise ValueError('Four source camera identities missing')
        values = [frame.get(key) for key in ('ego_x_m', 'ego_y_m', 'other_x_m', 'other_y_m')]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            raise ValueError('Both vehicle body poses missing')
        if frame.get('ego_heading') != '+x' or frame.get('other_heading') != '-x':
            raise ValueError('Opposing direction source missing')
        ego_x, ego_y, other_x, other_y = values
        if not (paved[0] <= ego_y <= paved[1] and paved[0] <= other_y <= paved[1]):
            raise ValueError('Vehicle body outside paved portion source')
        if ego_y + half_width > 0:
            ego_left_half.append(i)
        if other_y - half_width < 0:
            other_left_half.append(i)
        # Four-metre longitudinal body envelopes; overlap defines the sampled meeting.
        if abs(ego_x - other_x) <= 4:
            meeting.append(i)
    if not meeting:
        raise ValueError('No measured opposing meeting')
    return {'source_kind': setup['source_kind'], 'meeting_first_frame': meeting[0],
            'meeting_last_frame': meeting[-1], 'meeting_frames': len(meeting),
            'ego_left_half_during_meeting_frames': sum(i in ego_left_half for i in meeting),
            'other_left_half_during_meeting_frames': sum(i in other_left_half for i in meeting),
            'ego_first_left_half_frame': ego_left_half[0] if ego_left_half else None,
            'half_width_m': (paved[1] - paved[0]) / 2,
            'as_nearly_as_possible_judged': False,
            'native_body_geometry_proven': False, 'legal_conclusion': None}
