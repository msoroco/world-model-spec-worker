"""Measure original velocity only while the reviewed signed zone governs."""
import math

FRAMES = 600
CAMERAS = {'overview', 'approach', 'reference_corner', 'driver_reference'}
MPH_TO_MPS = 0.44704


def finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Invalid ' + name)
    return float(value)


def measure(context, rows):
    if context.get('source_kind') != 'reviewed_signed_speed_zone':
        raise ValueError('Missing signed-zone source review')
    for key in ('road_sha256', 'establishment_sha256', 'installed_sign_sha256', 'pixel_sha256'):
        value = context.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError('Missing source hash: ' + key)
    a, b = context.get('zone_bounds_m', (None, None))
    a, b = finite(a, 'zone start'), finite(b, 'zone end')
    authorized = finite(context.get('authorized_mph'), 'authorized mph')
    if not a < b or authorized <= 0:
        raise ValueError('Invalid signed-zone bounds or authorized value')
    if len(rows) != FRAMES:
        raise ValueError('Incomplete original speed trace')
    previous = -1
    in_zone = []
    speeds = []
    for i, row in enumerate(rows):
        if row.get('video_frame') != i or type(row.get('native_frame')) is not int or row['native_frame'] <= previous:
            raise ValueError('Original frame identity gap')
        previous = row['native_frame']
        if abs(finite(row.get('time_s'), 'original time') - i / 20) > 1e-6:
            raise ValueError('Original 20 Hz time join failed')
        cameras = row.get('source_cameras')
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[k] != i for k in CAMERAS):
            raise ValueError('Original camera frame join failed')
        position = finite(row.get('route_position_m'), 'original route position')
        speed = finite(row.get('observed_speed_mps'), 'original speed') / MPH_TO_MPS
        if speed < 0:
            raise ValueError('Negative original speed')
        in_zone.append(a <= position < b)
        speeds.append(speed)
    indices = [i for i, inside in enumerate(in_zone) if inside]
    if not indices or in_zone[0] or in_zone[-1]:
        raise ValueError('Complete entry and exit of signed zone not observed')
    return {'format': 'worker-source-signed-zone-measurement', 'frame_count': FRAMES,
        'rate_hz': 20, 'authorized_mph': authorized,
        'first_zone_frame': indices[0], 'last_zone_frame': indices[-1],
        'zone_frame_count': len(indices),
        'observed_speed_mph_range_in_zone': [min(speeds[i] for i in indices), max(speeds[i] for i in indices)],
        'frames_below_authorized_in_zone': sum(speeds[i] < authorized for i in indices),
        'frames_at_authorized_in_zone': sum(abs(speeds[i] - authorized) < 1e-9 for i in indices),
        'frames_above_authorized_in_zone': sum(speeds[i] > authorized for i in indices),
        'administrative_zone_establishment': context['zone_established'],
        'appropriate_installed_sign': context['appropriate_sign_installed'],
        'sign_governs_route': context['sign_governs_route'],
        'legal_compliance': 'unassessed', 'physical_acceptance_claimed': False}
