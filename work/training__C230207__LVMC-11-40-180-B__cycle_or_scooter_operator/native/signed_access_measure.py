"""Source geometry diagnostic for signed cycle/scooter access, no legal verdict."""
import json
import math
from pathlib import Path

FRAME_COUNT = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
ACTORS = ('bicycle', 'electric_bicycle', 'electric_scooter')


def derive(folder):
    folder = Path(folder)
    setup = json.loads((folder / 'setup.json').read_text())
    frames = json.loads((folder / 'raw-frames.json').read_text())
    if setup.get('source_kind') != 'synthetic_native_sample':
        raise ValueError('Source kind missing')
    if setup.get('actor_kind') not in ACTORS:
        raise ValueError('Covered machine source missing')
    if setup.get('surface_kind') not in ('sidewalk', 'roadway'):
        raise ValueError('Signed surface source missing')
    if setup.get('prohibition_sign_erected') is not True:
        raise ValueError('Erected prohibition sign source missing')
    if setup.get('sign_prohibits_actor') is not True:
        raise ValueError('Sign applicability source missing')
    zone = setup.get('governed_x_interval_m')
    if (not isinstance(zone, list) or len(zone) != 2 or
            not all(isinstance(x, (int, float)) and math.isfinite(x) for x in zone)
            or zone[0] >= zone[1]):
        raise ValueError('Sign-governed interval source missing')
    if len(frames) != FRAME_COUNT:
        raise ValueError('Incomplete riding history')
    inside = []
    for i, frame in enumerate(frames):
        if frame.get('frame') != i or abs(frame.get('elapsed_s', -1) - i / 20) > 1e-9:
            raise ValueError('Frame/time join failed')
        if tuple(frame.get('camera_ids', ())) != CAMERAS:
            raise ValueError('Four source camera identities missing')
        x, speed = frame.get('actor_x_m'), frame.get('actor_speed_mps')
        if (not isinstance(x, (int, float)) or not math.isfinite(x)
                or not isinstance(speed, (int, float)) or not math.isfinite(speed)):
            raise ValueError('Rider pose/speed source missing')
        if frame.get('riding_machine') is not True:
            raise ValueError('Riding state source missing')
        if zone[0] <= x <= zone[1]:
            inside.append(i)
    return {'source_kind': setup['source_kind'], 'actor_kind': setup['actor_kind'],
            'surface_kind': setup['surface_kind'], 'riding_frames': FRAME_COUNT,
            'inside_governed_segment_frames': len(inside),
            'first_inside_frame': inside[0] if inside else None,
            'administrative_authority_verified': False,
            'sign_pixels_verified': False, 'legal_conclusion': None}
