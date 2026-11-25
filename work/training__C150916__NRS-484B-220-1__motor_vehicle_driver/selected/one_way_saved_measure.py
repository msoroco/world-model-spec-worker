"""Measure original one-way travel from saved pose and independently sourced context.

This module never treats an authored R6-1 request as proof that a sign was
physically present, official, legible, or governing the observed road.
"""
import hashlib
import json
import math
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('road.xodr', 'road-context.json', 'road-review.json',
           'vehicle-pose.jsonl', 'video_frames.jsonl', 'trace.jsonl',
           'capture/evidence.jsonl', 'source_context/one_way_designation.txt',
           'source_context/sign_inventory.txt', 'source_context/sign_authority.txt',
           'source_context/sign_erection.txt', 'source_context/sign_governance.txt')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(row) for row in Path(path).read_text().splitlines()]


def measure(attempt, direction):
    attempt = Path(attempt)
    for name in (*SOURCES, *(name + '.mkv' for name in CAMERAS)):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    if direction not in ('designated', 'opposite'):
        raise ValueError('Unknown exact selected direction')
    context = json.loads((attempt / 'road-context.json').read_text())
    review = json.loads((attempt / 'road-review.json').read_text())
    if context.get('map_source_sha256') != sha(attempt / 'road.xodr'):
        raise ValueError('Original road source hash differs')
    if review.get('native_context_sha256') != sha(attempt / 'road-context.json'):
        raise ValueError('One-way road review binds another Native context')
    if context.get('requested_direction') != direction or review.get('requested_direction') != direction:
        raise ValueError('Original requested direction differs')
    for key in ('one_way_designation', 'sign_inventory', 'sign_authority',
                'sign_erection', 'sign_governance'):
        source = review.get(key)
        if (not isinstance(source, dict) or source.get('path') != 'source_context/' + key + '.txt'
                or source.get('sha256') != sha(attempt / source['path']) or not source.get('source_id')):
            raise ValueError('Independent one-way source differs: ' + key)
    poses = rows(attempt / 'vehicle-pose.jsonl')
    mapped = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    if any(len(items) != 600 for items in (poses, mapped, trace, evidence)):
        raise ValueError('Original 600-frame one-way source length differs')
    frame_ids = []
    traveled = 0.0
    on_road = 0
    wrong_way = 0
    for index, (pose, frame, state, packet) in enumerate(zip(poses, mapped, trace, evidence)):
        frame_id = pose.get('native_frame')
        if (pose.get('video_frame') != index or frame.get('video_frame') != index or
                frame_id != frame.get('native_frame') or frame_id != state.get('frame') or
                frame_id != packet.get('original_frame') or
                pose.get('camera_native_frames') != frame.get('camera_native_frames') or
                set(frame.get('camera_native_frames', {})) != set(CAMERAS)):
            raise ValueError('Original one-way frame/camera join differs')
        if any(value != frame_id for value in frame['camera_native_frames'].values()):
            raise ValueError('Original camera was not synchronized')
        if not math.isclose(pose['time_s'], frame['time_s'], abs_tol=1e-8):
            raise ValueError('Original pose and camera time differs')
        if not pose.get('footprint_corners_xy_m') or len(pose['footprint_corners_xy_m']) != 4:
            raise ValueError('Original vehicle footprint absent')
        if pose.get('requested_direction') != direction:
            raise ValueError('Original requested travel differs')
        position = state.get('position_m')
        velocity = state.get('velocity_mps')
        if (not isinstance(position, list) or len(position) != 3 or
                not isinstance(velocity, list) or len(velocity) != 3 or
                not all(math.isfinite(float(v)) for v in (*position, *velocity))):
            raise ValueError('Original one-way motion absent')
        if -100 <= position[0] <= 300:
            on_road += 1
        if velocity[0] < -0.5:
            wrong_way += 1
        if index:
            traveled += position[0] - trace[index-1]['position_m'][0]
        frame_ids.append(frame_id)
    if len(set(frame_ids)) != 600 or frame_ids != sorted(frame_ids):
        raise ValueError('Original one-way frame sequence differs')
    motion = 'designated' if traveled > 1 else 'opposite' if traveled < -1 else 'stationary'
    return {'case_direction_requested': direction, 'movement_direction_measured': motion,
            'signed_displacement_m': round(traveled, 3), 'on_governed_extent_frames': on_road,
            'opposite_velocity_frames': wrong_way,
            'roadway_designation_sourced': bool(review.get('roadway_is_one_way')),
            'sign_official_sourced': bool(review.get('sign_official')),
            'sign_erected_sourced': bool(review.get('sign_erected')),
            'sign_governs_road_sourced': bool(review.get('sign_governs_road')),
            'physical_sign_pixels_verified': bool(review.get('physical_sign_pixels_verified')),
            'source_hashes': {name: sha(attempt / name) for name in SOURCES},
            'physical_or_legal_acceptance': False}
