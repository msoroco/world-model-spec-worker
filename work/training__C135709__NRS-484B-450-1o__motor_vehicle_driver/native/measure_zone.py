"""Measure rest and body overlap with an authored device zone, without legal classification."""
import math

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Invalid ' + name)
    return float(value)


def measure(zone, observations):
    if len(observations) != FRAMES:
        raise ValueError('Incomplete original 600-frame source join')
    if not isinstance(zone, dict) or any(key not in zone for key in ('min_x', 'max_x', 'min_y', 'max_y')):
        raise ValueError('Missing governed zone geometry')
    if not finite(zone['min_x'], 'zone min x') < finite(zone['max_x'], 'zone max x'):
        raise ValueError('Invalid governed zone geometry')
    first = None
    rest = []
    overlap = []
    prior_native = -1
    for index, row in enumerate(observations):
        native = row.get('native_frame')
        if row.get('video_frame') != index or type(native) is not int or native <= prior_native:
            raise ValueError('Original frame identity gap')
        prior_native = native
        if abs(finite(row.get('time_s'), 'time') - index / 20) > 1e-6:
            raise ValueError('Original frame/time join differs')
        if row.get('source_cameras') != {name: index for name in CAMERAS}:
            raise ValueError('Four source camera join differs')
        speed = finite(row.get('observed_speed_mps'), 'speed')
        footprint = row.get('vehicle_footprint_m')
        if not isinstance(footprint, dict) or speed < 0:
            raise ValueError('Vehicle footprint or speed absent')
        for key in ('min_x', 'max_x', 'min_y', 'max_y'):
            finite(footprint.get(key), 'footprint ' + key)
        stopped = speed <= 0.10
        intersects = (min(footprint['max_x'], zone['max_x']) > max(footprint['min_x'], zone['min_x'])
                      and min(footprint['max_y'], zone['max_y']) > max(footprint['min_y'], zone['min_y']))
        rest.append(stopped)
        overlap.append(intersects)
        if stopped and first is None:
            first = index
    runs = []
    start = None
    for index, stopped in enumerate(rest + [False]):
        if stopped and start is None:
            start = index
        elif not stopped and start is not None:
            runs.append((start, index - 1))
            start = None
    longest = max(runs, key=lambda item: item[1] - item[0], default=None)
    if longest is None or longest[1] - longest[0] + 1 < 100:
        raise ValueError('No measured five-second stationary interval')
    segment = overlap[longest[0]:longest[1] + 1]
    return {'frame_count': FRAMES, 'rate_hz': 20, 'first_rest_frame': first,
            'rest_interval_frames': list(longest), 'rest_duration_s': len(segment) / 20,
            'zone_overlap_during_rest': all(segment), 'zone_overlap_frame_count': sum(segment),
            'legal_compliance': 'unassessed',
            'limitations': ['Authored zone and synthetic pixels do not establish official device authority.',
                            'Rest interval is a measured proxy; stop, stand, park, necessity and directions require independent review.']}
