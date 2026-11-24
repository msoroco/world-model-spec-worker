"""Saved-only turn geometry for unselected compatible signed-turn cells.

This checks original-source joins and engineering movement, not whether an
authorized sign legally governed the rider or whether posture was visible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from geometry import CELLS, FRAMES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError('Missing staged Native source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def _heading_change(start, end):
    return (end - start + 180) % 360 - 180


def _mean_heading(rows):
    values = [math.radians(r['native_heading_deg']) for r in rows]
    return math.degrees(math.atan2(sum(math.sin(v) for v in values),
                                    sum(math.cos(v) for v in values)))


def assess_geometry(native, config):
    if len(native) != FRAMES:
        raise ValueError('Native geometry frame count differs')
    direction, behavior = config['direction'], config['behavior']
    if direction not in CELLS or behavior not in ('obey', 'turn'):
        raise ValueError('Staged turn direction or behavior differs')
    cell, maneuver, sign, _ = CELLS[direction]
    if (config['cell_id'], config['maneuver'], config['sign_code']) != (cell, maneuver, sign):
        raise ValueError('Staged turn frozen identity differs')
    try:
        approach = native[190:210]
        exit_rows = native[550:570]
        start_heading = _mean_heading(approach)
        exit_heading = _mean_heading(exit_rows)
        delta = _heading_change(start_heading, exit_heading)
        start_xy = approach[0]['native_center_xy_m']
        exit_xy = exit_rows[-1]['native_center_xy_m']
        exit_roads = {r['native_road_id'] for r in exit_rows}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Original Native heading/body source missing') from exc
    if not all(math.isfinite(v) for v in (start_heading, exit_heading, delta, *start_xy, *exit_xy)):
        raise ValueError('Original Native geometry is nonfinite')
    expected_road = 2 if behavior == 'obey' else (3 if direction == 'right' else 4)
    if exit_roads != {expected_road}:
        raise ValueError('Original Native destination road differs')
    if behavior == 'obey':
        movement = abs(delta) <= 20 and abs(exit_xy[0] - start_xy[0]) < 2.5
    else:
        heading_sign = -1 if direction == 'right' else 1
        lateral_sign = 1 if direction == 'right' else -1
        movement = 60 <= heading_sign * delta <= 120 and lateral_sign * (exit_xy[0] - start_xy[0]) >= 6
    if not movement:
        raise ValueError('Original Native signed-turn geometry differs')
    return {'direction': direction, 'behavior': behavior, 'heading_change_deg': delta,
            'approach_heading_deg': start_heading, 'exit_heading_deg': exit_heading,
            'approach_xy_m': start_xy, 'exit_xy_m': exit_xy,
            'destination_road_id': expected_road, 'engineering_geometry_matched': True,
            'engineering_tolerances_not_legal': True,
            'posture_verified': False, 'official_sign_authorization_verified': False}


def _decode(path):
    if not path.is_file():
        raise ValueError('Missing staged source camera: ' + path.name)
    completed = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, timeout=180)
    if completed.returncode or completed.stdout.strip() != str(FRAMES):
        raise ValueError('Staged source camera full decode differs: ' + path.name)
    return {'sha256': sha(path), 'frames': FRAMES}


def audit_attempt(attempt):
    root = Path(attempt)
    config = json.loads((root / 'config.json').read_text())
    native = rows(root / 'native_samples.jsonl')
    frame_map = rows(root / 'video_frames.jsonl')
    rider = rows(root / 'rider_native_samples.jsonl')
    trace = rows(root / 'trace.jsonl')
    body = rows(root / 'body_history.jsonl')
    evidence = rows(root / 'capture/evidence.jsonl')
    if any(len(values) != FRAMES for values in (native, frame_map, rider, trace, body, evidence)):
        raise ValueError('Staged saved-source frame inventory differs')
    for index, (n, f, r, t, b, e) in enumerate(zip(native, frame_map, rider, trace, body, evidence)):
        frame = n['native_frame']
        time = n['time_s']
        if (f['video_frame'] != index or f['native_frame'] != frame or
                f['carla_frame'] != frame or r['frame'] != index or
                t['frame'] != frame or b['frame'] != frame or
                e['original_frame'] != frame or
                any(abs(source['time_s'] - time) > 1e-6 for source in (f, r, t))):
            raise ValueError('Staged original frame/time source join differs')
        if r['sign_id'] != ('11400803' if config['direction'] == 'right' else '11400804'):
            raise ValueError('Staged rider/sign source join differs')
        if r['machine_class'] != 'bicycle' or r['mounted'] is not None:
            raise ValueError('Staged source invented original posture')
    manifest = json.loads((root / 'capture/manifest.json').read_text())
    if manifest.get('frames') != FRAMES or manifest.get('extraction_confirmed') is not True or \
            manifest.get('acquisition') != 'original_live_run':
        raise ValueError('Staged original capture seal missing')
    survey = json.loads((root / 'sign-survey.json').read_text())
    expected_sign = '11400803' if config['direction'] == 'right' else '11400804'
    if survey.get('landmark_id') != expected_sign or survey.get('approach_road_id') != 1 or \
            survey.get('approach_lane_id') != -1:
        raise ValueError('Staged live sign/approach readback differs')
    if sha(root / 'authored-road.xodr') != config['road_sha256'] or \
            sha(root / 'source.jsonl') != config['source_sha256'] or \
            sha(root / 'road.xodr') != survey.get('native_map_sha256'):
        raise ValueError('Staged authored/live map or requested route source hash differs')
    geometry = assess_geometry(native, config)
    cameras = {name: _decode(root / (name + '.mkv')) for name in
               ('overview', 'approach', 'reference_corner', 'driver_reference')}
    return {'format': 'c104538-staged-native-saved-review-v1', 'case_id': config['case_id'],
            'source_kind': 'original_live_run', 'passed': True, 'accepted': False,
            'geometry': geometry, 'cameras': cameras,
            'source_sha256': {name: sha(root / name) for name in
                ('native_samples.jsonl', 'video_frames.jsonl', 'rider_native_samples.jsonl',
                 'trace.jsonl', 'body_history.jsonl', 'capture/evidence.jsonl',
                 'capture/manifest.json', 'sign-survey.json', 'authored-road.xodr',
                 'road.xodr', 'source.jsonl')},
            'posture_verified': False, 'official_sign_authorization_verified': False,
            'original_pixels_reviewed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit_attempt(args.attempt), sort_keys=True))
