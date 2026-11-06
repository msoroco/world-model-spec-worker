"""Source-bound no-countdown pedestrian signal timing; no statutory verdict."""
import hashlib
import json
import math
from pathlib import Path

from geometry import check as check_geometry

RATE_HZ = 20
FRAMES = 240


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def signal_state(index, flash_start_s, steady_start_s=9):
    if type(index) is not int or index < 0 or index >= FRAMES:
        raise ValueError('Signal frame outside full capture')
    if flash_start_s not in (.5, 2) or steady_start_s != 9:
        raise ValueError('No-countdown control phase differs')
    time_s = index / RATE_HZ
    if time_s < flash_start_s:
        return 'walk', True
    if time_s < steady_start_s:
        return 'dont_walk_flashing', (index // 5) % 2 == 0
    return 'dont_walk_steady', True


def point(value, label):
    if not isinstance(value, list) or len(value) != 2 or any(
        type(x) not in (int, float) or not math.isfinite(x) for x in value
    ):
        raise ValueError('Invalid original ' + label)
    return tuple(float(x) for x in value)


def measure(samples_path, context_path):
    samples_path, context_path = Path(samples_path), Path(context_path)
    for path in (samples_path, context_path):
        if not path.is_file():
            raise ValueError('Missing required source: ' + path.name)
    road = context_path.parent / 'road.xodr'
    if not road.is_file():
        raise ValueError('Missing required source: road.xodr')
    context = json.loads(context_path.read_text())
    if context.get('authored_map_sha256') != sha(road):
        raise ValueError('No-countdown authored map hash differs')
    geometry = check_geometry(road)
    if (geometry['near_edge_x_m'], geometry['far_edge_x_m']) != (-3.5, 3.5):
        raise ValueError('No-countdown highway edge geometry differs')
    kind = context.get('source_kind')
    if kind not in ('synthetic_scene_request', 'native_observation'):
        raise ValueError('No-countdown source provenance missing')
    if context.get('countdown_present') is not False:
        raise ValueError('No-countdown context does not exclude a countdown')
    if context.get('device_governs_crosswalk') is not True or context.get('device_faces_pedestrian') is not True:
        raise ValueError('Governing pedestrian direction not established')
    if kind == 'native_observation' and (
        not context.get('native_map_sha256') or not context.get('display_pixel_audit_sha256')
    ):
        raise ValueError('Native no-countdown original map and pixel provenance missing')
    origin = point(context.get('near_highway_edge_xy_m'), 'near highway edge')
    direction = point(context.get('crossing_forward_xy'), 'crossing direction')
    if abs(math.hypot(*direction) - 1) > .001 or context.get('highway_span_m') != 7:
        raise ValueError('No-countdown crossing geometry differs')
    rows = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows) != FRAMES:
        raise ValueError('Full 240-frame no-countdown source required')
    previous = None
    entry = clearance = flash = steady = None
    seen = set()
    flash_lights = set()
    prior_phase = -1
    for index, row in enumerate(rows):
        frame, time = row.get('native_frame'), row.get('time_s')
        if type(frame) is not int or type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError('No-countdown frame/time invalid')
        if previous is not None and (frame != previous['native_frame'] + 1 or abs(time - previous['time_s'] - .05) > .002):
            raise ValueError('No-countdown source frame/time order invalid')
        if row.get('crosswalk_id') != context.get('crosswalk_id') or row.get('device_id') != context.get('device_id'):
            raise ValueError('No-countdown source identity differs')
        if 'displayed_countdown_s' in row or row.get('countdown_visible') is not False:
            raise ValueError('Countdown absent condition not established')
        indication = row.get('indication')
        if indication not in ('walk', 'dont_walk_flashing', 'dont_walk_steady'):
            raise ValueError('No-countdown pedestrian indication invalid')
        phase = {'walk': 0, 'dont_walk_flashing': 1, 'dont_walk_steady': 2}[indication]
        if phase < prior_phase or phase > prior_phase + 1:
            raise ValueError('No-countdown phase sequence reverses or skips')
        prior_phase = phase
        if type(row.get('display_illuminated')) is not bool:
            raise ValueError('No-countdown illumination missing')
        if indication == 'dont_walk_flashing':
            flash_lights.add(row['display_illuminated'])
        elif not row['display_illuminated']:
            raise ValueError('Walk or steady indication not illuminated')
        if kind == 'native_observation' and not row.get('original_display_frame_sha256'):
            raise ValueError('Native no-countdown display frame missing')
        seen.add(indication)
        pose = point(row.get('pedestrian_xy_m'), 'pedestrian pose')
        body = row.get('pedestrian_footprint_xy_m')
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError('Original pedestrian footprint missing')
        vertices = [point(value, 'pedestrian footprint') for value in body]
        if len(set(vertices)) != 4 or math.dist(pose, (sum(v[0] for v in vertices)/4,
                                                       sum(v[1] for v in vertices)/4)) > .05:
            raise ValueError('Original pedestrian pose/footprint differs')
        progress = [sum((value[i] - origin[i]) * direction[i] for i in (0, 1)) for value in vertices]
        if entry is None and max(progress) > 0:
            entry = (previous, row)
        if clearance is None and min(progress) >= 7:
            clearance = (previous, row)
        if flash is None and indication == 'dont_walk_flashing':
            flash = (previous, row)
        if steady is None and indication == 'dont_walk_steady':
            steady = (previous, row)
        previous = row
    if seen != {'walk', 'dont_walk_flashing', 'dont_walk_steady'} or flash_lights != {True, False}:
        raise ValueError('Complete Walk/flashing/steady cycle missing')
    if any(event is None or event[0] is None for event in (entry, clearance, flash, steady)):
        raise ValueError('Entry, full clearance, flash or steady event not bracketed')
    if not entry[1]['native_frame'] < clearance[1]['native_frame'] < steady[1]['native_frame']:
        raise ValueError('Crossing/steady event order differs')
    if flash[1]['native_frame'] >= steady[1]['native_frame']:
        raise ValueError('No-countdown phase order differs')
    entry_state = entry[1]['indication']
    if entry_state not in ('walk', 'dont_walk_flashing'):
        raise ValueError('Pedestrian first entry lacks controlled state')
    def bracket(event):
        return {'first_frame': event[1]['native_frame'],
                'time_interval_s': [event[0]['time_s'], event[1]['time_s']]}
    return {'format': 'c10316-no-countdown-observation-v1',
            'source_sha256': {samples_path.name: sha(samples_path), context_path.name: sha(context_path),
                              road.name: sha(road)},
            'source_kind': kind, 'original_frames': len(rows), 'rate_hz': RATE_HZ,
            'first_entry': bracket(entry), 'entry_indication': entry_state,
            'flashing_start': bracket(flash), 'full_body_clearance': bracket(clearance),
            'steady_start': bracket(steady), 'clearance_before_steady': True,
            'lawful_prior_entry_proven': False, 'governing_device_observed': kind == 'native_observation',
            'exceptions_reviewed': False, 'legal_verdict_claimed': False}
