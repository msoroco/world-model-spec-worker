"""Source-bound direction meter for the C238396 roundabout proposal.

The signed area of consecutive radial positions measures translational motion.
Positive area is counterclockwise in the authored OpenDRIVE x/y frame. Neither
vehicle yaw nor a requested label is accepted as evidence of travel direction.
"""

import json
import math
from pathlib import Path

CENTER = (22.0, 0.0)
HZ = 20
FRAMES = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def check_config(config):
    expected = ('training__C238396__LVMC-11-43-010-A__motor_vehicle_driver'
                '__probe_a', 'training__C238396__LVMC-11-43-010-A__motor_vehicle_driver'
                '__probe_b')
    if (config.get('case_id') not in expected or config.get('law_id') != 'LVMC-11-43-010-A'
            or config.get('cell_id') != 'C238396' or config.get('actor') != 'motor_vehicle_driver'
            or config.get('duration_s') != 30 or config.get('rate_hz') != HZ
            or config.get('frames') != FRAMES or config.get('physical_completion') is not False
            or config.get('legal_verdict') is not None):
        raise ValueError('C238396 exact duration, scope or outcome differs')
    if tuple(c.get('name') for c in config.get('cameras', ())) != CAMERAS:
        raise ValueError('Four named source cameras required')
    if any(c.get('fps') != HZ or not all(c.get(k) for k in
           ('width', 'height', 'fov_deg', 'location_xyz_m', 'rotation_pyr_deg'))
           for c in config['cameras']):
        raise ValueError('Source camera geometry incomplete')
    if config.get('observed_source_required') is not True:
        raise ValueError('Observed original positions required for legal analysis')
    return {'case_id': config['case_id'], 'frames': FRAMES,
            'source_cameras': list(CAMERAS), 'physical_completion': False,
            'carla_contacted': False}


def measure(rows, source_kind):
    """Measure a complete frame-joined source; synthetic requests stay diagnostics."""
    if source_kind not in ('original_native', 'authored_native_request'):
        raise ValueError('Source kind is not allowed')
    if len(rows) != FRAMES:
        raise ValueError('Full 600-frame source required')
    signed = []
    phase_counts = {'inside_roundabout': 0, 'outside_roundabout': 0}
    previous = None
    for i, row in enumerate(rows):
        tolerance = .01 if source_kind == 'original_native' else 1e-8
        if row.get('frame') != i or abs(row.get('time_s', -1) - (i + 1) / HZ) > tolerance:
            raise ValueError('Frame/time join differs')
        if row.get('source_kind') != source_kind:
            raise ValueError('Frame source differs')
        xy = row.get('ego_xy_m')
        if not isinstance(xy, list) or len(xy) != 2 or not all(
                isinstance(v, (int, float)) and math.isfinite(v) for v in xy):
            raise ValueError('Original x/y source missing')
        if row.get('inside_roundabout') is not True:
            phase_counts['outside_roundabout'] += 1
            previous = None
            continue
        phase_counts['inside_roundabout'] += 1
        radial = (xy[0] - CENTER[0], xy[1] - CENTER[1])
        radius = math.hypot(*radial)
        # This broad authored-road annulus checks context. It is not a legal
        # directional tolerance and never substitutes for Native map readback.
        if not 14.5 <= radius <= 23.5:
            raise ValueError('Frame outside authored circulatory annulus')
        if previous is not None:
            cross = previous[0] * radial[1] - previous[1] * radial[0]
            signed.append(cross)
        previous = radial
    if len(signed) < HZ * 10:
        raise ValueError('Insufficient within-roundabout translational window')
    positives = sum(v > 0.01 for v in signed)
    negatives = sum(v < -0.01 for v in signed)
    return {'format': 'c238396-direction-meter-v1', 'source_kind': source_kind,
            'source_frames': len(rows), 'within_frames': phase_counts['inside_roundabout'],
            'positive_step_count': positives, 'negative_step_count': negatives,
            'signed_radial_cross_sum_m2': sum(signed),
            'translational_direction': ('counterclockwise' if positives > 0 and negatives == 0
                else 'clockwise' if negatives > 0 and positives == 0 else 'mixed_or_unknown'),
            'physical_completion': False,
            'original_native_observed': source_kind == 'original_native'}


def read_and_measure(path, source_kind):
    return measure([json.loads(line) for line in Path(path).read_text().splitlines()],
                   source_kind)
