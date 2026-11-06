"""Measure a flashing pedestrian countdown crossing from synchronized source frames.

This measures event timing and source completeness. It never assigns a statutory
verdict or asserts an exception is absent from synthetic observations.
"""
import hashlib
import json
import math
from pathlib import Path
from geometry import check as check_geometry

RATE_HZ = 20
FRAMES = 240


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value, label):
    if not isinstance(value, list) or len(value) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError('Invalid original ' + label)
    return tuple(float(v) for v in value)


def measure(samples_path, context_path):
    samples_path, context_path = Path(samples_path), Path(context_path)
    for path in (samples_path, context_path):
        if not path.is_file():
            raise ValueError('Missing required source: ' + path.name)
    context = json.loads(context_path.read_text())
    road_path = context_path.parent / 'road.xodr'
    if not road_path.is_file():
        raise ValueError('Missing required source: road.xodr')
    if context.get('authored_map_sha256') != sha(road_path):
        raise ValueError('Authored crossing map source hash differs')
    geometry = check_geometry(road_path)
    if geometry['near_edge_x_m'] != -3.5 or geometry['far_edge_x_m'] != 3.5:
        raise ValueError('Authored crossing edge geometry differs')
    kind = context.get('source_kind')
    if kind not in ('synthetic_scene_request', 'native_observation'):
        raise ValueError('Unrecognized countdown source provenance')
    if not context.get('crosswalk_id') or not context.get('device_id') or not context.get('highway_boundary_source'):
        raise ValueError('Missing crosswalk, governing device, or highway boundary source')
    if context.get('device_governs_crosswalk') is not True or context.get('device_faces_pedestrian') is not True:
        raise ValueError('Governing pedestrian direction not established')
    origin = point(context.get('near_highway_edge_xy_m'), 'near highway edge')
    direction = point(context.get('crossing_forward_xy'), 'crossing direction')
    if abs(math.hypot(*direction) - 1) > .001:
        raise ValueError('Crossing direction must be unit length')
    span = context.get('highway_span_m')
    if type(span) not in (int, float) or not math.isfinite(span) or span < 2:
        raise ValueError('Invalid highway span')
    if kind == 'native_observation' and (
        not context.get('native_map_sha256') or not context.get('display_pixel_audit_sha256') or
        context.get('observed_frame_count') != FRAMES
    ):
        raise ValueError('Native countdown needs map, original pixel, and frame provenance')
    rows = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows) != FRAMES:
        raise ValueError('Full 240-frame countdown source required')
    previous = None
    event_rows = []
    positive_lights = set()
    first_entry = None
    first_full_clearance = None
    zero = None
    progress_trace = []
    for row in rows:
        frame, time = row.get('native_frame'), row.get('time_s')
        if type(frame) is not int or type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError('Invalid countdown frame/time')
        if previous is not None and (frame != previous['native_frame'] + 1 or abs(time - previous['time_s'] - 1/RATE_HZ) > .002):
            raise ValueError('Countdown frame/time order or rate invalid')
        if row.get('crosswalk_id') != context['crosswalk_id'] or row.get('device_id') != context['device_id']:
            raise ValueError('Countdown source identity differs')
        displayed = row.get('displayed_countdown_s')
        if type(displayed) is not int or displayed < 0 or displayed > 99:
            raise ValueError('Legible original displayed countdown missing')
        flashing = ('dont_walk_flashing', 'wait_flashing', 'upraised_hand_flashing')
        if row.get('indication') not in (flashing if displayed > 0 else flashing + ('dont_walk_steady', 'wait_steady', 'upraised_hand_steady')):
            raise ValueError('Flashing pedestrian indication missing before zero or invalid at zero')
        if type(row.get('display_illuminated')) is not bool:
            raise ValueError('Original display illumination missing')
        if displayed > 0:
            positive_lights.add(row['display_illuminated'])
        if previous is not None and (displayed > previous['displayed_countdown_s'] or displayed < previous['displayed_countdown_s'] - 1):
            raise ValueError('Displayed countdown jumps or increases')
        if kind == 'native_observation' and not row.get('original_display_frame_sha256'):
            raise ValueError('Original display frame provenance missing')
        pose = point(row.get('pedestrian_xy_m'), 'pedestrian position')
        footprint = row.get('pedestrian_footprint_xy_m')
        if not isinstance(footprint, list) or len(footprint) != 4:
            raise ValueError('Original pedestrian footprint missing')
        vertices = [point(p, 'pedestrian footprint') for p in footprint]
        if len(set(vertices)) != 4 or math.dist(pose, (sum(v[0] for v in vertices)/4, sum(v[1] for v in vertices)/4)) > .05:
            raise ValueError('Original pedestrian footprint and pose differ')
        projected = [sum((v[i] - origin[i])*direction[i] for i in (0, 1)) for v in vertices]
        front, rear = max(projected), min(projected)
        progress_trace.append((front, rear))
        if first_entry is None and front > 0:
            first_entry = (previous, row)
        if first_full_clearance is None and rear >= span:
            first_full_clearance = (previous, row)
        if zero is None and displayed == 0:
            if previous is None or previous['displayed_countdown_s'] == 0:
                raise ValueError('Countdown zero transition not bracketed')
            zero = (previous, row)
        event_rows.append((frame, time, displayed))
        previous = row
    if first_entry is None or first_full_clearance is None or zero is None:
        raise ValueError('Crossing entry, full clearance, or displayed zero missing')
    if positive_lights != {True, False}:
        raise ValueError('Original flashing illumination cycle missing')
    if first_entry[0] is None or first_entry[1]['native_frame'] >= first_full_clearance[1]['native_frame']:
        raise ValueError('Crossing entry and clearance are not ordered')
    if first_entry[1]['native_frame'] >= zero[1]['native_frame']:
        raise ValueError('Crossing did not enter during positive countdown')
    if any(b[0] < a[0] - .02 or b[1] < a[1] - .02 for a, b in zip(progress_trace, progress_trace[1:])):
        raise ValueError('Pedestrian crossing reverses or jumps backward')
    if progress_trace[0][0] >= 0 or progress_trace[-1][1] < span:
        raise ValueError('Crossing source does not span both highway edges')
    def bracket(event):
        return {'first_frame': event[1]['native_frame'], 'time_interval_s': [event[0]['time_s'], event[1]['time_s']]}
    clearance = bracket(first_full_clearance)
    zero_event = bracket(zero)
    c0, c1 = clearance['time_interval_s']
    z0, z1 = zero_event['time_interval_s']
    relation = 'before_zero' if c1 < z0 else 'at_or_after_zero' if c0 >= z1 else 'sampling_overlap_unresolved'
    return {
        'format': 'c10316-flashing-countdown-observation-v1',
        'source_sha256': {samples_path.name: sha(samples_path), context_path.name: sha(context_path),
                          road_path.name: sha(road_path)},
        'source_kind': kind, 'original_frames': len(rows), 'rate_hz': RATE_HZ,
        'entry': bracket(first_entry), 'full_body_clearance': clearance, 'displayed_zero': zero_event,
        'clearance_relative_to_displayed_zero': relation,
        'governing_device_observed': kind == 'native_observation',
        'highway_boundary_observed': kind == 'native_observation',
        'exceptions_reviewed': False, 'legal_verdict_claimed': False,
    }
