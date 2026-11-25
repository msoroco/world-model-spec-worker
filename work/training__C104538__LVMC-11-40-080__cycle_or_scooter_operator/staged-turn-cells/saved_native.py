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


def _decode(path, expected_size):
    if not path.is_file():
        raise ValueError('Missing staged source camera: ' + path.name)
    completed = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries',
        'stream=nb_read_frames,width,height,r_frame_rate',
        '-of', 'json', str(path)],
        capture_output=True, text=True, timeout=180)
    if completed.returncode:
        raise ValueError('Staged source camera full decode differs: ' + path.name)
    try:
        streams = json.loads(completed.stdout)['streams']
        stream = streams[0]
        actual = (int(stream['width']), int(stream['height']))
        numerator, denominator = map(int, stream['r_frame_rate'].split('/'))
        matched = (len(streams) == 1 and int(stream['nb_read_frames']) == FRAMES and
                   actual == expected_size and denominator > 0 and
                   numerator / denominator == 20)
    except (ValueError, KeyError, IndexError, TypeError, ZeroDivisionError) as exc:
        raise ValueError('Staged source camera metadata missing: ' + path.name) from exc
    if not matched:
        raise ValueError('Staged source camera full decode differs: ' + path.name)
    return {'sha256': sha(path), 'frames': FRAMES, 'size': list(actual), 'fps': 20}


def check_original_body_join(native, rider, trace, body, evidence):
    """Bind the observed rider to the same Native body and captured actor."""
    actor_id = rider.get('actor_id')
    position = trace.get('position_m')
    original = evidence.get('ego', {})
    evidence_position = original.get('position_m')
    vertices = native.get('native_body_vertices_m')
    body_vertices = body.get('body_vertices_m')
    evidence_vertices = original.get('body_vertices_m')
    if type(actor_id) is not int or evidence.get('actor_id') != actor_id:
        raise ValueError('Staged original rider actor identity differs')
    if (not isinstance(position, list) or len(position) < 2 or
            not isinstance(evidence_position, list) or len(evidence_position) < 2 or
            not isinstance(vertices, list) or len(vertices) != 8 or
            not isinstance(body_vertices, list) or not isinstance(evidence_vertices, list) or
            len(vertices) != len(body_vertices) or len(vertices) != len(evidence_vertices)):
        raise ValueError('Staged original body/trace source missing')
    if any(abs(a - b) > 1e-3 for source in (position, evidence_position)
           for a, b in zip(source[:2], native['native_center_xy_m'])):
        raise ValueError('Staged original rider/trace position differs')
    for source in (body_vertices, evidence_vertices):
        for expected, observed in zip(vertices, source):
            if len(expected) != 3 or len(observed) != 3 or any(
                    abs(a - b) > 1e-3 for a, b in zip(expected, observed)):
                raise ValueError('Staged original body source differs')


def check_map_source_join(root, config, survey):
    root = Path(root)
    if sha(root / 'authored-road.xodr') != config['road_sha256'] or \
            sha(root / 'road.xodr') != survey.get('native_map_sha256') or \
            sha(root / 'source.jsonl') != config['source_sha256'] or \
            sha(root / 'native-map.xodr') != survey.get('native_map_sha256'):
        raise ValueError('Staged authored/live map or requested route source hash differs')


SEALED_SOURCES = (
    'construction.json', 'runner.py', 'config.json', 'road.xodr',
    'authored-road.xodr', 'native-map.xodr', 'source.jsonl',
    'native_samples.jsonl', 'rider_native_samples.jsonl',
    'video_frames.jsonl', 'trace.jsonl', 'body_history.jsonl',
    'capture/evidence.jsonl', 'capture/manifest.json', 'sign-survey.json',
    'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
    'driver_reference.mkv', 'raw.mkv',
)


def check_capture_seal(root, expected_frames=FRAMES):
    root = Path(root)
    seal_path = root / 'capture-seal.json'
    if not seal_path.is_file():
        raise ValueError('Staged original capture seal missing')
    seal = json.loads(seal_path.read_text())
    if (seal.get('format') != 'worker-sealed-capture' or
            seal.get('provenance_kind') != 'native' or
            seal.get('diagnostic_fixture') is not False or
            seal.get('frames') != expected_frames or
            seal.get('restoration', {}).get('restored') is not True or
            seal.get('events') != ['capture_finished', 'encoders_closed',
                                   'restoration_verified'] or
            any(code != 0 for code in seal.get('encoder_exit_codes', {}).values())):
        raise ValueError('Staged original capture seal differs')
    for name in SEALED_SOURCES:
        path = root / name
        if not path.is_file() or seal.get('sources', {}).get(name) != sha(path):
            raise ValueError('Staged original sealed source differs: ' + name)
    revisions = seal.get('native_revision', {})
    if (revisions.get('construction_sha256') != sha(root / 'construction.json') or
            revisions.get('runner_sha256') != sha(root / 'runner.py')):
        raise ValueError('Staged original sealed construction differs')
    return seal


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
                abs(e['recording_time_s'] - time) > 1e-6 or
                any(abs(source['time_s'] - time) > 1e-6 for source in (f, r, t))):
            raise ValueError('Staged original frame/time source join differs')
        if r['sign_id'] != ('11400803' if config['direction'] == 'right' else '11400804'):
            raise ValueError('Staged rider/sign source join differs')
        if r['machine_class'] != 'bicycle' or r['mounted'] is not None:
            raise ValueError('Staged source invented original posture')
        check_original_body_join(n, r, t, b, e)
    manifest = json.loads((root / 'capture/manifest.json').read_text())
    if manifest.get('frames') != FRAMES or manifest.get('extraction_confirmed') is not True or \
            manifest.get('acquisition') != 'original_live_run':
        raise ValueError('Staged original capture seal missing')
    check_capture_seal(root)
    survey = json.loads((root / 'sign-survey.json').read_text())
    expected_sign = '11400803' if config['direction'] == 'right' else '11400804'
    if survey.get('landmark_id') != expected_sign or survey.get('approach_road_id') != 1 or \
            survey.get('approach_lane_id') != -1:
        raise ValueError('Staged live sign/approach readback differs')
    check_map_source_join(root, config, survey)
    geometry = assess_geometry(native, config)
    cameras = {name: _decode(root / (name + '.mkv'), size) for name, size in (
               ('overview', (1920, 1080)), ('approach', (1280, 720)),
               ('reference_corner', (1280, 720)),
               ('driver_reference', (1280, 720)))}
    return {'format': 'c104538-staged-native-saved-review-v1', 'case_id': config['case_id'],
            'source_kind': 'original_live_run', 'passed': True, 'accepted': False,
            'geometry': geometry, 'cameras': cameras,
            'source_sha256': {name: sha(root / name) for name in
                ('native_samples.jsonl', 'video_frames.jsonl', 'rider_native_samples.jsonl',
                 'trace.jsonl', 'body_history.jsonl', 'capture/evidence.jsonl',
                 'capture/manifest.json', 'sign-survey.json', 'authored-road.xodr',
                 'road.xodr', 'native-map.xodr', 'source.jsonl')},
            'posture_verified': False, 'official_sign_authorization_verified': False,
            'original_pixels_reviewed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit_attempt(args.attempt), sort_keys=True))
