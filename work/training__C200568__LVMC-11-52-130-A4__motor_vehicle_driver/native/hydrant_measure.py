"""Saved geometry diagnostic for LVMC 11.52.130(A)(4), not legal acceptance."""
import json
import math
from pathlib import Path

FRAME_COUNT = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def distance_point_rectangle(point, rectangle):
    hx, hy = point
    x0, y0, x1, y1 = rectangle
    if not all(math.isfinite(v) for v in (hx, hy, x0, y0, x1, y1)) or x0 > x1 or y0 > y1:
        raise ValueError('Invalid measured hydrant/vehicle geometry')
    return math.hypot(max(x0 - hx, 0, hx - x1), max(y0 - hy, 0, hy - y1))


def derive(folder):
    folder = Path(folder)
    setup = json.loads((folder / 'setup.json').read_text())
    frames = json.loads((folder / 'raw-frames.json').read_text())
    if setup.get('source_kind') != 'synthetic_native_sample':
        raise ValueError('Source kind missing')
    regime = setup.get('parking_permission_source')
    if regime not in ('parallel_permitted', 'angle_permitted', 'no_parking_permitted'):
        raise ValueError('Parking permission source missing')
    threshold = 15.0 if regime == 'parallel_permitted' else 20.0
    point = setup.get('hydrant_point_ft')
    if not isinstance(point, list) or len(point) != 2:
        raise ValueError('Hydrant source missing')
    uncertainty = setup.get('distance_uncertainty_ft')
    if (not isinstance(uncertainty, (int, float)) or not math.isfinite(uncertainty)
            or uncertainty < 0):
        raise ValueError('Distance uncertainty source missing')
    if len(frames) != FRAME_COUNT:
        raise ValueError('Incomplete stopped interval source')
    distances = []
    for i, frame in enumerate(frames):
        if frame.get('frame') != i or abs(frame.get('elapsed_s', -1) - i / 20) > 1e-9:
            raise ValueError('Frame/time join failed')
        if tuple(frame.get('camera_ids', ())) != CAMERAS:
            raise ValueError('Four source camera identities missing')
        speed = frame.get('ego_speed_mps')
        if not isinstance(speed, (int, float)) or not math.isfinite(speed):
            raise ValueError('Vehicle speed source missing')
        if speed > 0.05:
            raise ValueError('Subject did not remain stopped')
        footprint = frame.get('ego_footprint_ft')
        if not isinstance(footprint, list) or len(footprint) != 4:
            raise ValueError('Vehicle footprint source missing')
        distances.append(distance_point_rectangle(point, footprint))
    closest = min(distances)
    low, high = max(0.0, closest - uncertainty), closest + uncertainty
    relation = 'inside' if high < threshold else 'outside' if low > threshold else 'overlaps'
    return {'source_kind': setup['source_kind'], 'parking_permission_source': regime,
            'applicable_threshold_ft': threshold, 'stopped_frames': FRAME_COUNT,
            'closest_footprint_distance_ft': closest,
            'distance_bracket_ft': [low, high], 'threshold_relation': relation,
            'exception_context_declarations': setup.get('exception_context_declarations', {}),
            'exception_source_verified': False,
            'paint_or_sign_used_to_set_distance': False,
            'engineering_stop_threshold_mps': 0.05,
            'native_geometry_proven': False, 'legal_conclusion': None}
