"""Source facts for the prior-entry exception of NRS 484B.283(1)(d)(4)."""
import hashlib
import json
import math
from pathlib import Path


def signal_state(index, entry_program):
    if type(index) is not int or index < 0 or index >= 240:
        raise ValueError('Prior-entry signal frame outside capture')
    if entry_program not in ('walk', 'flashing_no_countdown'):
        raise ValueError('Prior-entry signal program invalid')
    if index >= 80:
        return 'dont_walk_steady', True
    if entry_program == 'flashing_no_countdown' and index >= 10:
        return 'dont_walk_flashing', (index // 5) % 2 == 0
    return 'walk', True


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value, label):
    if not isinstance(value, list) or len(value) != 2 or any(
        type(v) not in (int, float) or not math.isfinite(v) for v in value
    ):
        raise ValueError('Invalid original ' + label)
    return tuple(float(v) for v in value)


def measure(samples_path, context_path):
    samples_path, context_path = Path(samples_path), Path(context_path)
    road = context_path.parent / 'road.xodr'
    for path in (samples_path, context_path, road):
        if not path.is_file():
            raise ValueError('Missing required source: ' + path.name)
    context = json.loads(context_path.read_text())
    if context.get('authored_map_sha256') != sha(road):
        raise ValueError('Prior-entry map hash differs')
    if context.get('source_kind') not in ('synthetic_scene_request', 'native_observation'):
        raise ValueError('Prior-entry provenance missing')
    if context.get('device_governs_crosswalk') is not True or context.get('device_faces_pedestrian') is not True:
        raise ValueError('Prior-entry governing direction not established')
    if context.get('countdown_present') is not False or context.get('highway_span_m') != 7:
        raise ValueError('Prior-entry source control differs')
    origin = point(context.get('near_highway_edge_xy_m'), 'near edge')
    direction = point(context.get('crossing_forward_xy'), 'crossing direction')
    if abs(math.hypot(*direction) - 1) > .001:
        raise ValueError('Prior-entry crossing direction invalid')
    kind = context['source_kind']
    if kind == 'native_observation' and (
        not context.get('native_map_sha256') or not context.get('display_pixel_audit_sha256')
    ):
        raise ValueError('Native prior-entry map or pixel provenance missing')
    rows = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows) != 240:
        raise ValueError('Full 240-frame prior-entry source required')
    phase_rank = {'walk': 0, 'dont_walk_flashing': 1, 'dont_walk_steady': 2}
    first_entry = steady = clearance = None
    previous = None
    prior_rank = 0
    flashing_lights = set()
    progress_after_steady = []
    for index, row in enumerate(rows):
        frame, time = row.get('native_frame'), row.get('time_s')
        if type(frame) is not int or type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError('Prior-entry frame/time invalid')
        if previous is not None and (frame != previous['native_frame'] + 1 or abs(time - previous['time_s'] - .05) > .002):
            raise ValueError('Prior-entry frame/time order invalid')
        if row.get('crosswalk_id') != context.get('crosswalk_id') or row.get('device_id') != context.get('device_id'):
            raise ValueError('Prior-entry source identity differs')
        indication = row.get('indication')
        if indication not in phase_rank or phase_rank[indication] < prior_rank or (
            phase_rank[indication] > prior_rank + 1 and indication != 'dont_walk_steady'
        ):
            raise ValueError('Prior-entry phase sequence invalid')
        prior_rank = phase_rank[indication]
        if row.get('countdown_visible') is not False or 'displayed_countdown_s' in row:
            raise ValueError('Prior-entry unexpected countdown')
        if type(row.get('display_illuminated')) is not bool:
            raise ValueError('Prior-entry illumination missing')
        if indication == 'dont_walk_flashing':
            flashing_lights.add(row['display_illuminated'])
        elif not row['display_illuminated']:
            raise ValueError('Prior-entry Walk or steady not illuminated')
        if kind == 'native_observation' and not row.get('original_display_frame_sha256'):
            raise ValueError('Native prior-entry display frame missing')
        pose = point(row.get('pedestrian_xy_m'), 'pedestrian pose')
        body = row.get('pedestrian_footprint_xy_m')
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError('Prior-entry pedestrian footprint missing')
        vertices = [point(v, 'pedestrian footprint') for v in body]
        if len(set(vertices)) != 4 or math.dist(pose, (sum(v[0] for v in vertices)/4,
                                                       sum(v[1] for v in vertices)/4)) > .05:
            raise ValueError('Prior-entry pedestrian pose/footprint differs')
        projected = [sum((v[i] - origin[i]) * direction[i] for i in (0, 1)) for v in vertices]
        if first_entry is None and max(projected) > 0:
            first_entry = (previous, row)
        if steady is None and indication == 'dont_walk_steady':
            steady = (previous, row)
        if clearance is None and min(projected) >= 7:
            clearance = (previous, row)
        if indication == 'dont_walk_steady' and 0 < max(projected) and min(projected) < 7:
            progress_after_steady.append((time, min(projected)))
        previous = row
    if any(event is None or event[0] is None for event in (first_entry, steady, clearance)):
        raise ValueError('Prior entry, steady and clearance events must be bracketed')
    if not first_entry[1]['native_frame'] < steady[1]['native_frame'] < clearance[1]['native_frame']:
        raise ValueError('Prior-entry event order differs')
    entry_indication = first_entry[1]['indication']
    if entry_indication not in ('walk', 'dont_walk_flashing'):
        raise ValueError('Prior-entry indication is not controlled')
    if entry_indication == 'dont_walk_flashing' and flashing_lights != {True, False}:
        raise ValueError('Prior-entry flashing illumination cycle absent')
    if not progress_after_steady or any(b[1] < a[1] - .001 for a, b in
                                        zip(progress_after_steady, progress_after_steady[1:])):
        raise ValueError('Prior-entry crossing did not continue toward far edge')
    def bracket(event):
        return {'first_frame': event[1]['native_frame'],
                'time_interval_s': [event[0]['time_s'], event[1]['time_s']]}
    return {'format': 'c10316-prior-entry-source-observation-v1',
            'source_sha256': {path.name: sha(path) for path in (samples_path, context_path, road)},
            'source_kind': kind, 'original_frames': 240, 'rate_hz': 20,
            'first_entry': bracket(first_entry), 'entry_indication': entry_indication,
            'steady_start': bracket(steady), 'full_body_clearance': bracket(clearance),
            'post_steady_crossing_samples': len(progress_after_steady),
            'continued_progress_source_fact': True,
            'lawful_prior_entry_proven': False, 'as_soon_as_possible_bound_declared': False,
            'exceptions_reviewed': False, 'physical_signal_observed': False,
            'legal_verdict_claimed': False}
