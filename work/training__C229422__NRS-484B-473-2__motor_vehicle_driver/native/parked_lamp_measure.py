"""Source-state diagnostic for NRS 484B.473(2), without optical inference."""
import json
import math
from pathlib import Path

FRAME_COUNT = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def lamp_command(mode):
    """Draft Native light-state request; display and dimming remain sourced facts."""
    if mode not in ('dimmed', 'full', 'cowl', 'parking'):
        raise ValueError('Unsupported parked lamp mode')
    return {'headlamps_on': mode in ('dimmed', 'full'),
            'headlamp_intensity_request': 0.4 if mode == 'dimmed' else (
                1.0 if mode == 'full' else 0.0),
            'cowl_lamps_on': mode == 'cowl',
            'parking_lamps_on': mode == 'parking'}


def derive(folder):
    folder = Path(folder)
    setup = json.loads((folder / 'setup.json').read_text())
    frames = json.loads((folder / 'raw-frames.json').read_text())
    if setup.get('source_kind') != 'synthetic_native_sample':
        raise ValueError('Source kind missing')
    if setup.get('nighttime_clock_source') is not True:
        raise ValueError('Nighttime clock source missing')
    if setup.get('highway_location_source') is not True:
        raise ValueError('Highway location source missing')
    if setup.get('lawful_parking_review') != 'unverified':
        raise ValueError('Lawful parking review must remain separate')
    if len(frames) != FRAME_COUNT:
        raise ValueError('Incomplete parked interval source')
    dimmed = full = cowl_or_parking = 0
    for i, frame in enumerate(frames):
        if frame.get('frame') != i or abs(frame.get('elapsed_s', -1) - i / 20) > 1e-9:
            raise ValueError('Frame/time join failed')
        if tuple(frame.get('camera_ids', ())) != CAMERAS:
            raise ValueError('Four source camera identities missing')
        speed = frame.get('ego_speed_mps')
        if not isinstance(speed, (int, float)) or not math.isfinite(speed):
            raise ValueError('Parked speed source missing')
        if speed > 0.05:
            raise ValueError('Vehicle did not remain parked')
        mode = frame.get('lamp_mode_source')
        if mode not in ('dimmed', 'full', 'cowl', 'parking'):
            raise ValueError('Displayed lamp state source missing')
        dimmed += mode == 'dimmed'
        full += mode == 'full'
        cowl_or_parking += mode in ('cowl', 'parking')
    return {'source_kind': setup['source_kind'], 'parked_frames': FRAME_COUNT,
            'dimmed_headlamp_frames': dimmed, 'full_headlamp_frames': full,
            'cowl_or_parking_lamp_frames': cowl_or_parking,
            'cowl_or_parking_exception_present': cowl_or_parking > 0,
            'engineering_stop_threshold_mps': 0.05,
            'lamp_intensity_is_native_pixel_verified': False,
            'lawful_parking_verified': False, 'legal_conclusion': None}
