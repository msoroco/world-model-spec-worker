"""Source geometry diagnostic for signed cycle/scooter access, no legal verdict."""
import json
import math
import hashlib
from pathlib import Path

FRAME_COUNT = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
ACTORS = ('bicycle', 'electric_bicycle', 'electric_scooter')


def derive(folder, *, require_original=False):
    folder = Path(folder)
    setup = json.loads((folder / 'setup.json').read_text())
    frames = json.loads((folder / 'raw-frames.json').read_text())
    source_kind = setup.get('source_kind')
    if source_kind not in ('synthetic_native_sample', 'original_native_review'):
        raise ValueError('Source kind missing')
    if require_original and source_kind != 'original_native_review':
        raise ValueError('Original Native sign review required')
    if source_kind == 'original_native_review':
        sources = setup.get('source_files')
        if not isinstance(sources, dict) or set(sources) != {'sign_pixels', 'director_determination', 'roadway_access'}:
            raise ValueError('Original sign and authority sources missing')
        for item in sources.values():
            if not isinstance(item, dict) or not item.get('path') or not item.get('sha256'):
                raise ValueError('Original sign source binding missing')
            name = Path(item['path'])
            if name.is_absolute() or '..' in name.parts:
                raise ValueError('Unsafe sign source path')
            path = (folder / name).resolve()
            if folder.resolve() not in path.parents or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Original sign source hash differs')
        if setup.get('sign_pixels_verified') is not True or setup.get('administrative_authority_verified') is not True:
            raise ValueError('Original sign pixels or determination unverified')
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
    if len(frames) != FRAME_COUNT and not (source_kind == 'synthetic_native_sample'
                                          and setup.get('diagnostic_excerpt') is True
                                          and 2 <= len(frames) <= 2000):
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
            'surface_kind': setup['surface_kind'], 'riding_frames': len(frames),
            'diagnostic_excerpt': len(frames) != FRAME_COUNT,
            'inside_governed_segment_frames': len(inside),
            'first_inside_frame': inside[0] if inside else None,
            'administrative_authority_verified': source_kind == 'original_native_review',
            'sign_pixels_verified': source_kind == 'original_native_review',
            'legal_conclusion': None}
