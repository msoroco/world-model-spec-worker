"""Source-bound CPU observation of a police officer controlling an ego approach.

This reports source facts only. An officer's presence or a scripted instruction
alone is insufficient to establish actual control or the statutory exception.
"""
import hashlib
import json
import math
from pathlib import Path
from shapely.geometry import MultiPoint, Polygon

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
REQUIRED = ('officer_context.json', 'officer_history.jsonl', 'officer_review.json',
            'signal_context.json', 'signal_history.jsonl', 'video_frames.jsonl')
GESTURES = ('stop', 'proceed', 'hold', 'none')


def _read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Missing finite ' + name)
    return float(value)


def analyze(root):
    root = Path(root)
    hashes = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError('Missing original source: ' + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / 'officer_context.json').read_text())
    signal = json.loads((root / 'signal_context.json').read_text())
    for key in ('native_map_id', 'intersection_id', 'ego_road_id', 'ego_lane_id'):
        if context.get(key) != signal.get(key):
            raise ValueError('Officer source differs from selected signed entrance: ' + key)
    officer_id = context.get('native_officer_actor_id')
    if type(officer_id) not in (int, str) or not str(officer_id):
        raise ValueError('Original officer actor identity required')
    if context.get('officer_assignment_source') is None:
        raise ValueError('Officer assignment source required')
    if context.get('controlled_approach_lane') != [signal['ego_road_id'], signal['ego_lane_id']]:
        raise ValueError('Officer does not govern selected ego entrance')
    polygon = Polygon(signal.get('intersection_polygon_xy_m', []))
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Original intersection geometry required')
    histories = [_read_rows(root / name) for name in
                 ('officer_history.jsonl', 'signal_history.jsonl', 'video_frames.jsonl')]
    officers, signals, frames = histories
    if len(officers) < 3 or not (len(officers) == len(signals) == len(frames)):
        raise ValueError('Incomplete original officer/signal/frame history')
    review = json.loads((root / 'officer_review.json').read_text())
    if review.get('provenance_kind') not in ('original_source_review', 'synthetic_fixture'):
        raise ValueError('Officer review provenance required')
    if review.get('officer_history_sha256') != hashes['officer_history.jsonl'] or \
       review.get('video_frames_sha256') != hashes['video_frames.jsonl']:
        raise ValueError('Officer review source hash differs from original bytes')
    camera_hashes = review.get('camera_sha256')
    if not isinstance(camera_hashes, dict) or set(camera_hashes) != set(CAMERAS):
        raise ValueError('Four source-camera hashes required')
    for camera in CAMERAS:
        path = root / (camera + '.mkv')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != camera_hashes[camera]:
            raise ValueError('Officer review camera bytes differ: ' + camera)
    observations = review.get('frames')
    if not isinstance(observations, list) or len(observations) != len(officers):
        raise ValueError('Complete per-frame officer review required')
    previous = (-1, -math.inf)
    first_control = None
    first_entry = None
    for index, (officer, source, frame, observed) in enumerate(zip(officers, signals, frames, observations)):
        fid, time = source.get('frame'), _finite(source.get('time_s'), 'source time')
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError('Nonmonotone original source history')
        previous = fid, time
        if any(row.get('frame') != fid or _finite(row.get('time_s'), 'joined time') != time
               for row in (officer,)) or frame.get('carla_frame') != fid or frame.get('time_s') != time:
            raise ValueError('Officer source frame/time join failed')
        if frame.get('video_frame') != index or set(frame.get('camera_frames', {})) != set(CAMERAS) or \
           any(frame['camera_frames'][name] != fid for name in CAMERAS):
            raise ValueError('Four original camera frame joins required')
        if observed.get('frame') != fid or observed.get('video_frame') != index:
            raise ValueError('Officer review frame join failed')
        if officer.get('native_officer_actor_id') != officer_id or \
           officer.get('controlled_approach_lane') != context['controlled_approach_lane']:
            raise ValueError('Officer identity or governed lane changed')
        gesture = officer.get('control_gesture')
        if gesture not in GESTURES or observed.get('observed_gesture') not in GESTURES:
            raise ValueError('Officer gesture observation missing')
        controls = officer.get('officer_controls_ego')
        if type(controls) is not bool or type(observed.get('officer_visible')) is not bool:
            raise ValueError('Officer control or visibility observation missing')
        if [source.get('ego_road_id'), source.get('ego_lane_id')] != context['controlled_approach_lane']:
            raise ValueError('Ego left officer-governed entrance')
        vertices = source.get('ego_body_vertices_xy_m')
        if not isinstance(vertices, list) or len(vertices) < 4:
            raise ValueError('Complete original ego body required')
        body = MultiPoint([(_finite(p[0], 'body x'), _finite(p[1], 'body y'))
                           for p in vertices]).convex_hull
        if body.area <= 0:
            raise ValueError('Degenerate original ego body')
        inside = body.intersects(polygon)
        if index == 0 and inside:
            raise ValueError('Missing pre-entry original body history')
        if inside and first_entry is None:
            first_entry = {'frame': fid, 'time_s': time, 'officer_controls_ego': controls,
                           'observed_gesture': observed['observed_gesture']}
        if controls:
            if not observed['officer_visible'] or observed['observed_gesture'] != gesture or gesture == 'none':
                raise ValueError('Officer control lacks matching original-camera gesture')
            if first_control is None:
                first_control = {'frame': fid, 'time_s': time, 'gesture': gesture}
    if first_entry is None:
        raise ValueError('No original ego body entry')
    return {'format': 'worker-officer-control-observations', 'sources': hashes,
            'native_officer_actor_id': officer_id, 'controlled_approach_lane': context['controlled_approach_lane'],
            'first_observed_control': first_control, 'first_ego_entry': first_entry,
            'officer_controls_ego_at_entry_observed': first_entry['officer_controls_ego'] and
            first_entry['observed_gesture'] != 'none', 'provenance_kind': review['provenance_kind'],
            'physical_control_verified': False, 'legal_exception_judgment': 'unresolved',
            'legal_conclusion': 'unresolved'}
