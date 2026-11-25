"""Independent integrity audit of a saved crest finalizer's derived files.

This verifies source joins and declared observations. It never asserts physical
visibility, legal hazard, highway designation, or local acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from saved_crest import CASE_SUFFIXES, ONE_WAY_AUTHORITY, REQUIRED_SOURCES, measure, source_inventory


def _lines(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'derived file missing or linked: {path.name}')
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def audit(attempt_dir, *, assignment_id, case_id, expected_frames=900):
    if case_id not in {f'{assignment_id}__{suffix}' for suffix in CASE_SUFFIXES}:
        raise ValueError('wrong exact crest case')
    attempt = Path(attempt_dir).resolve()
    manifest = attempt / 'source-hashes.json'
    if not manifest.exists():
        provenance = attempt / 'acquisition-provenance.json'
        if (provenance.is_file() and
                json.loads(provenance.read_text()).get('diagnostic_fixture') is True):
            manifest = attempt / 'original-hashes.json'
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError('sealed original source manifest missing')
    manifest_bytes = manifest.read_bytes()
    hashes = json.loads(manifest_bytes)
    source_inventory(hashes, case_id, expected_frames)
    observation = measure(attempt, hashes, case_id=case_id,
                          assignment_id=assignment_id, expected_frames=expected_frames)
    original_body = _lines(attempt / 'frames.jsonl')
    original_rays = _lines(attempt / 'crest-rays.jsonl')
    trace_path = attempt / 'crest-derived-trace.jsonl'
    trace = _lines(trace_path if trace_path.is_file() else attempt / 'trace.jsonl')
    if trace_path.is_file():
        core_trace = _lines(attempt / 'trace.jsonl')
        if len(core_trace) != len(trace) or any(
                core.get('frame') != derived['frame'] or
                abs(core.get('time_s', -1) - derived['time_s']) > 1e-4 or
                (('opposing_body_distance_m' in core) and core != derived)
                for core, derived in zip(core_trace, trace)):
            raise ValueError('derived trace differs from original Core trace')
    frame_map = _lines(attempt / 'video_frames.jsonl')
    if len(trace) != expected_frames or len(frame_map) != expected_frames:
        raise ValueError('derived frame count differs from sealed originals')
    cameras = ('overview', 'approach', 'reference_corner', 'driver_reference')
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
                or (mapping.get('camera_frames') is not None and
                    mapping.get('camera_frames') != {name: body['frame'] for name in cameras})):
            raise ValueError('derived frame map differs from sealed Native packets')
    result_path = attempt / 'result.json'
    if result_path.is_symlink() or not result_path.is_file():
        raise ValueError('derived Native result missing or linked')
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if (result.get('case_id') != case_id or result.get('measured_values') != observation
            or result.get('trace_reference') != 'trace.jsonl'
            or result.get('video_frame_map_reference') != 'video_frames.jsonl'
            or result.get('video_references') != [f'{name}.mkv' for name in cameras]):
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
    evidence = result.get('recording_evidence')
    expected_channels = {item['name'] for item in result['recording_description']['channels']}
    if (not isinstance(evidence, list) or
            {item.get('name') for item in evidence} != expected_channels):
        raise ValueError('derived recording evidence inventory differs')
    for item in evidence:
        reference = item.get('reference')
        if reference != 'channels/' + item['name'] + '.jsonl':
            raise ValueError('derived recording evidence reference differs')
        rows = _lines(attempt / reference)
        if len(rows) != expected_frames or any(
                row.get('time_s') != body['timestamp_s'] or 'value' not in row
                for row, body in zip(rows, original_body)):
            raise ValueError('derived recording evidence frame join differs')
    if (result.get('setup_confirmed') is not False
            or result.get('maneuver_completed') is not False):
        raise ValueError('unreviewed physical completion claimed in derived result')
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != hashlib.sha256(manifest_bytes).hexdigest():
        raise ValueError('original source manifest changed during derived audit')
    return {'format': 'c104084-crest-derived-audit-v1', 'case_id': case_id,
            'source_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'derived_sha256': {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                               for name in ('trace.jsonl', 'video_frames.jsonl', 'result.json')},
            'verified_frames': expected_frames, 'source_join_passed': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
