"""Saved-source diagnostic for NRS 484D.165(3), without legal inference."""
import json
import math
from pathlib import Path

FRAME_COUNT = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
THRESHOLDS_FT = {'ambient_reveal': 1000.0, 'front_white_or_amber': 500.0,
                 'rear_red': 500.0}


def bracket_relation(probe, threshold):
    if not isinstance(probe, dict):
        raise ValueError('Numeric optical probe source missing')
    value = probe.get('estimated_distance_ft')
    uncertainty = probe.get('uncertainty_ft')
    if (not isinstance(value, (int, float)) or not math.isfinite(value)
            or not isinstance(uncertainty, (int, float))
            or not math.isfinite(uncertainty) or uncertainty < 0):
        raise ValueError('Invalid numeric optical probe')
    low, high = value - uncertainty, value + uncertainty
    relation = 'below' if high < threshold else 'above' if low > threshold else 'overlaps'
    return {'estimate_ft': value, 'uncertainty_ft': uncertainty,
            'bracket_ft': [low, high], 'threshold_ft': threshold,
            'threshold_relation': relation, 'source_is_native_pixels': False}


def derive(folder):
    folder = Path(folder)
    setup = json.loads((folder / 'setup.json').read_text())
    frames = json.loads((folder / 'raw-frames.json').read_text())
    if setup.get('source_kind') != 'synthetic_native_sample':
        raise ValueError('Source kind missing')
    if setup.get('night_hours_source') is not True:
        raise ValueError('Lighting hours source missing')
    if setup.get('adjacent_paved_shoulder_source') is not True:
        raise ValueError('Shoulder geometry source missing')
    probes = setup.get('optical_probes', {})
    optics = {key: bracket_relation(probes.get(key), threshold)
              for key, threshold in THRESHOLDS_FT.items()}
    if len(frames) != FRAME_COUNT:
        raise ValueError('Incomplete stopped interval source')
    off_front, off_rear, wrong_near_side = [], [], []
    for i, frame in enumerate(frames):
        if frame.get('frame') != i or abs(frame.get('elapsed_s', -1) - i / 20) > 1e-9:
            raise ValueError('Frame/time join failed')
        if tuple(frame.get('camera_ids', ())) != CAMERAS:
            raise ValueError('Four source camera identities missing')
        speed = frame.get('ego_speed_mps')
        if not isinstance(speed, (int, float)) or not math.isfinite(speed):
            raise ValueError('Stopped vehicle speed source missing')
        if speed > 0.05:
            raise ValueError('Subject did not remain stopped')
        if frame.get('front_lamp_color') not in ('white', 'amber', 'off'):
            raise ValueError('Front lamp source missing')
        if frame.get('rear_lamp_color') not in ('red', 'off'):
            raise ValueError('Rear lamp source missing')
        if frame.get('near_traffic_lamp_side') not in ('left', 'right'):
            raise ValueError('Near-traffic lamp side source missing')
        if frame['front_lamp_color'] == 'off':
            off_front.append(i)
        if frame['rear_lamp_color'] == 'off':
            off_rear.append(i)
        if frame['near_traffic_lamp_side'] != setup.get('passing_traffic_side'):
            wrong_near_side.append(i)
    return {'source_kind': setup['source_kind'], 'stopped_frames': FRAME_COUNT,
            'front_off_frames': len(off_front), 'rear_off_frames': len(off_rear),
            'wrong_near_traffic_side_frames': len(wrong_near_side),
            'optical_brackets': optics, 'engineering_stop_threshold_mps': 0.05,
            'native_pixel_visibility_proven': False, 'legal_conclusion': None}
