"""Source-bound steady pedestrian indication timing; no statutory verdict."""
import hashlib
import json
import math
from pathlib import Path

RATE_HZ = 20
FRAMES = 240


def signal_state(index, steady_start_s):
    if type(index) is not int or index < 0 or index >= FRAMES:
        raise ValueError('Steady signal frame outside capture')
    if steady_start_s not in (.5, 4.0):
        raise ValueError('Steady controlled transition differs')
    return ('walk' if index / RATE_HZ < steady_start_s else 'dont_walk_steady', True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value, label):
    if not isinstance(value, list) or len(value) != 2 or any(
        type(x) not in (int, float) or not math.isfinite(x) for x in value
    ):
        raise ValueError('Invalid original ' + label)
    return tuple(float(x) for x in value)


def measure(samples_path, context_path):
    samples_path, context_path = Path(samples_path), Path(context_path)
    road_path = context_path.parent / 'road.xodr'
    for path in (samples_path, context_path, road_path):
        if not path.is_file():
            raise ValueError('Missing required source: ' + path.name)
    context = json.loads(context_path.read_text())
    if context.get('authored_map_sha256') != sha(road_path):
        raise ValueError('Steady authored map hash differs')
    if context.get('source_kind') not in ('synthetic_scene_request', 'native_observation'):
        raise ValueError('Steady source provenance missing')
    if context.get('device_governs_crosswalk') is not True or context.get('device_faces_pedestrian') is not True:
        raise ValueError('Steady source governing direction not established')
    if context.get('highway_span_m') != 7:
        raise ValueError('Steady source highway span differs')
    origin = point(context.get('near_highway_edge_xy_m'), 'near edge')
    direction = point(context.get('crossing_forward_xy'), 'crossing direction')
    if abs(math.hypot(*direction) - 1) > .001:
        raise ValueError('Steady source crossing direction invalid')
    if context['source_kind'] == 'native_observation' and (
        not context.get('native_map_sha256') or not context.get('display_pixel_audit_sha256')
    ):
        raise ValueError('Native steady map or pixel provenance missing')
    rows = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows) != FRAMES:
        raise ValueError('Full 240-frame steady source required')
    previous = None
    entry = steady = clearance = None
    progress_after_steady = []
    phase = 0
    for index, row in enumerate(rows):
        frame, time = row.get('native_frame'), row.get('time_s')
        if type(frame) is not int or type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError('Steady frame/time invalid')
        if previous is not None and (frame != previous['native_frame'] + 1 or abs(time - previous['time_s'] - .05) > .002):
            raise ValueError('Steady frame/time order invalid')
        if row.get('crosswalk_id') != context.get('crosswalk_id') or row.get('device_id') != context.get('device_id'):
            raise ValueError('Steady source identity differs')
        indication = row.get('indication')
        if indication not in ('walk', 'dont_walk_steady') or row.get('display_illuminated') is not True:
            raise ValueError('Steady illuminated indication invalid')
        if indication == 'walk' and phase:
            raise ValueError('Steady indication reversed')
        if indication == 'dont_walk_steady':
            phase = 1
            if steady is None:
                steady = (previous, row)
        if context['source_kind'] == 'native_observation' and not row.get('original_display_frame_sha256'):
            raise ValueError('Native steady display frame missing')
        pose = point(row.get('pedestrian_xy_m'), 'pedestrian pose')
        footprint = row.get('pedestrian_footprint_xy_m')
        if not isinstance(footprint, list) or len(footprint) != 4:
            raise ValueError('Steady pedestrian footprint missing')
        vertices = [point(value, 'pedestrian footprint') for value in footprint]
        if len(set(vertices)) != 4 or math.dist(pose, (sum(v[0] for v in vertices)/4,
                                                       sum(v[1] for v in vertices)/4)) > .05:
            raise ValueError('Steady pedestrian pose/footprint differs')
        projections = [sum((v[i] - origin[i]) * direction[i] for i in (0, 1)) for v in vertices]
        if entry is None and max(projections) > 0:
            entry = (previous, row)
        if clearance is None and min(projections) >= 7:
            clearance = (previous, row)
        if phase and min(projections) < 7 and max(projections) > 0:
            progress_after_steady.append((time, min(projections)))
        previous = row
    if any(event is None or event[0] is None for event in (entry, steady, clearance)):
        raise ValueError('Entry, steady, or full clearance not bracketed')
    if not steady[1]['native_frame'] < clearance[1]['native_frame']:
        raise ValueError('Steady transition did not precede clearance')
    if not progress_after_steady:
        raise ValueError('No crossing interval after steady indication')
    increments = [b[1] - a[1] for a, b in zip(progress_after_steady, progress_after_steady[1:])]
    if any(delta < -.001 for delta in increments):
        raise ValueError('Reversal after steady indication')
    relation = 'before_steady' if entry[1]['native_frame'] < steady[1]['native_frame'] else 'at_or_after_steady'
    def bracket(event):
        return {'first_frame': event[1]['native_frame'],
                'time_interval_s': [event[0]['time_s'], event[1]['time_s']]}
    return {'format': 'c10316-steady-source-observation-v1',
            'source_sha256': {path.name: sha(path) for path in (samples_path, context_path, road_path)},
            'source_kind': context['source_kind'], 'original_frames': FRAMES, 'rate_hz': RATE_HZ,
            'first_entry': bracket(entry), 'steady_start': bracket(steady),
            'full_body_clearance': bracket(clearance), 'entry_relative_to_steady': relation,
            'post_steady_crossing_samples': len(progress_after_steady),
            'minimum_post_steady_progress_m_per_frame': min(increments) if increments else None,
            'as_soon_as_possible_bound_declared': False, 'lawful_prior_entry_proven': False,
            'exceptions_reviewed': False, 'physical_signal_observed': False,
            'legal_verdict_claimed': False}
