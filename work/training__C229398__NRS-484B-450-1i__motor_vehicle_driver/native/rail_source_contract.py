"""Build a rail footprint measurement packet from sealed original Native rows.

The CPU fixture for this module tests joins and rejection only. It is never
physical railroad evidence or a legal finding.
"""

import hashlib
import json
import math
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def _lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def _footprint(row):
    x, y = row['vehicle_center_xy_m']
    ex, ey = row['vehicle_half_extent_xy_m']
    yaw = float(row['vehicle_yaw_rad'])
    values = (x, y, ex, ey, yaw)
    if not all(type(v) in (int, float) and math.isfinite(v) for v in values) or ex <= 0 or ey <= 0:
        raise ValueError('Original vehicle pose or extent invalid')
    c, s = math.cos(yaw), math.sin(yaw)
    return [[x + dx*c - dy*s, y + dx*s + dy*c]
            for dx, dy in ((ex, ey), (ex, -ey), (-ex, -ey), (-ex, ey))]


def load_original(root, case_id):
    root = Path(root)
    survey_file = root / 'original-rail-survey.json'
    rows_file = root / 'original-native-rows.jsonl'
    map_file = root / 'video_frames.jsonl'
    seal_file = root / 'original-source-seal.json'
    seal = read(seal_file)
    if seal.get('format') != 'original-rail-native-source-seal' or seal.get('case_id') != case_id:
        raise ValueError('Wrong original rail source seal')
    expected = {'original-rail-survey.json', 'original-native-rows.jsonl', 'video_frames.jsonl'}
    expected |= {name + '.mkv' for name in CAMERAS}
    if set(seal.get('sha256', {})) != expected:
        raise ValueError('Incomplete original rail source seal')
    for name in expected:
        if sha(root / name) != seal['sha256'][name]:
            raise ValueError('Original rail source changed: ' + name)
    survey = read(survey_file)
    if (survey.get('source_kind') != 'original_native_rail_survey' or
            survey.get('case_id') != case_id or
            survey.get('review_status') != 'original_geometry_pending_independent_review' or
            len(survey.get('rails', [])) < 2):
        raise ValueError('Original physical rail survey missing')
    rails = []
    for rail in survey['rails']:
        if (rail.get('source_kind') not in ('map_survey', 'native_survey') or
                not rail.get('source_ref') or len(rail.get('polyline_xy_m', [])) < 2):
            raise ValueError('Original physical rail source incomplete')
        rails.append(rail)
    rows, maps = _lines(rows_file), _lines(map_file)
    if len(rows) != 600 or len(maps) != 600:
        raise ValueError('Original rail source requires 600 joined frames')
    frames = []
    for index, (row, frame_map) in enumerate(zip(rows, maps)):
        frame = row.get('native_frame')
        if (row.get('source_kind') != 'original_native' or
                row.get('case_id') != case_id or
                row.get('video_frame') != index or
                frame_map.get('native_frame') != frame or
                frame_map.get('video_frame') != index or
                frame_map.get('camera_native_frames') != {name: frame for name in CAMERAS}):
            raise ValueError('Original rail Native/frame/camera join differs')
        time_s = index / 20
        if abs(float(row.get('time_s', -1)) - time_s) > 1e-6 or abs(float(frame_map.get('time_s', -1)) - time_s) > 1e-6:
            raise ValueError('Original rail 20 Hz time join differs')
        if not row.get('vehicle_actor_id') or not row.get('pose_source_ref') or not row.get('extent_source_ref') or not row.get('speed_source_ref'):
            raise ValueError('Original vehicle Native source missing')
        reason = row.get('halt_reason', 'unknown')
        if reason != 'unknown' and not row.get('halt_reason_source_ref'):
            raise ValueError('Halt reason lacks original source')
        frames.append({'frame': index, 'sim_time_s': time_s,
                       'pose_source_ref': row['pose_source_ref'],
                       'extent_source_ref': row['extent_source_ref'],
                       'speed_source_ref': row['speed_source_ref'],
                       'vehicle_footprint_xy_m': _footprint(row),
                       'speed_mps': row['speed_mps'],
                       'halt_reason': reason,
                       'halt_reason_source_ref': row.get('halt_reason_source_ref')})
    return {'format': 'rail-footprint-native-source-v1', 'rails': rails, 'frames': frames,
            'original_source_seal_sha256': sha(seal_file),
            'original_rail_survey_sha256': sha(survey_file),
            'original_pixels_reviewed': False,
            'legal_verdict_claimed': False}
