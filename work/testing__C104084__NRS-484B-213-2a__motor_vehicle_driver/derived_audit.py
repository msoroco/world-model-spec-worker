"""Independent integrity audit of a saved crest finalizer's derived files.

This verifies source joins and declared observations. It never asserts physical
visibility, legal hazard, highway designation, or local acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from saved_crest import CASE_SUFFIXES, ONE_WAY_AUTHORITY, REQUIRED_SOURCES, measure


def _lines(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'derived file missing or linked: {path.name}')
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def audit(attempt_dir, *, assignment_id, case_id, expected_frames=900):
    if case_id not in {f'{assignment_id}__{suffix}' for suffix in CASE_SUFFIXES}:
        raise ValueError('wrong exact crest case')
    attempt = Path(attempt_dir).resolve()
    manifest = attempt / 'source-hashes.json'
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError('sealed original source manifest missing')
    manifest_bytes = manifest.read_bytes()
    hashes = json.loads(manifest_bytes)
    required = set(REQUIRED_SOURCES)
    if case_id.endswith('__left_one_way_obstructed'):
        required.add(ONE_WAY_AUTHORITY)
    if not isinstance(hashes, dict) or set(hashes) != required:
        raise ValueError('sealed original source manifest has wrong exact sources')
    observation = measure(attempt, hashes, case_id=case_id,
                          assignment_id=assignment_id, expected_frames=expected_frames)
    original_body = _lines(attempt / 'frames.jsonl')
    original_rays = _lines(attempt / 'crest-rays.jsonl')
    trace = _lines(attempt / 'trace.jsonl')
    frame_map = _lines(attempt / 'video_frames.jsonl')
    if len(trace) != expected_frames or len(frame_map) != expected_frames:
        raise ValueError('derived frame count differs from sealed originals')
    cameras = ('forward', 'left', 'right', 'rear')
    for index, (body, ray, row, mapping) in enumerate(zip(original_body, original_rays,
                                                           trace, frame_map)):
        if row != {'frame': body['frame'], 'time_s': body['timestamp_s'],
                   'ego_body_corners_signed_m': body['ego_body_corners_signed_m'],
                   'opposing_body_distance_m': body['opposing_body_distance_m'],
                   'opposing_body_corner_ray_hits': ray['body_corner_ray_hits']}:
            raise ValueError('derived trace differs from sealed Native packets')
        if (mapping.get('video_frame') != index or mapping.get('carla_frame') != body['frame']
                or mapping.get('native_frame') != body['frame']
                or mapping.get('time_s') != body['timestamp_s']
                or mapping.get('camera_frames') != {name: body['frame'] for name in cameras}):
            raise ValueError('derived frame map differs from sealed Native packets')
    result_path = attempt / 'result.json'
    if result_path.is_symlink() or not result_path.is_file():
        raise ValueError('derived Native result missing or linked')
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if (result.get('case_id') != case_id or result.get('measured_values') != observation
            or result.get('trace_reference') != 'trace.jsonl'
            or result.get('video_frame_map_reference') != 'video_frames.jsonl'
            or result.get('video_references') != [f'camera-{name}.mp4' for name in cameras]):
        raise ValueError('derived Native result differs from sealed observation')
    expected_left = not case_id.endswith('__right_crest_obstructed')
    expected_blocked = not case_id.endswith('__left_crest_clear')
    expected_checks = (
        ('left-side body motion', expected_left, bool(observation['ego_body_left_side_frames'])),
        ('all-corner proxy-ray blockage', expected_blocked,
         bool(observation['all_corner_rays_blocked_frames'])),
        ('body and view condition on one original frame', True,
         bool(observation['body_and_view_target_frames'])),
    )
    checks = result.get('target_checks')
    if not isinstance(checks, list) or len(checks) != len(expected_checks):
        raise ValueError('derived target checks missing or altered')
    for check, (name, requested, measured) in zip(checks, expected_checks):
        if (check.get('target') != name or check.get('requested') != requested
                or check.get('measured') != measured
                or check.get('matched') != (requested == measured)
                or check.get('physical_cause_confirmed') is not False
                or check.get('cause_evidence') != observation['source_sha256']):
            raise ValueError('derived target check differs from sealed observation')
    if (result.get('setup_confirmed') is not False
            or result.get('maneuver_completed') is not False
            or result.get('recording_evidence') != []):
        raise ValueError('unreviewed physical completion claimed in derived result')
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != hashlib.sha256(manifest_bytes).hexdigest():
        raise ValueError('original source manifest changed during derived audit')
    return {'format': 'c104084-crest-derived-audit-v1', 'case_id': case_id,
            'source_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'derived_sha256': {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                               for name in ('trace.jsonl', 'video_frames.jsonl', 'result.json')},
            'verified_frames': expected_frames, 'source_join_passed': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
