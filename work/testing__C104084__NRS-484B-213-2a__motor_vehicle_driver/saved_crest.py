"""Source-bound saved-attempt crest observations; no legal hazard decision.

The caller supplies the original attempt directory and a manifest of byte hashes.
This code reads recorded packets only and never repairs or synthesizes evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


REQUIRED_SOURCES = ('frames.jsonl', 'lane-context.json', 'crest-rays.jsonl',
                    'frame-map.json', 'overview.mkv', 'approach.mkv',
                    'reference_corner.mkv', 'driver_reference.mkv')
ONE_WAY_AUTHORITY = 'one-way-authority.json'
PNG_MANIFEST = 'original-png-manifest.json'
ROAD_PROFILE = 'road-profile.json'
REVIEWED_COMMON = ('reviewed-highway.json', 'reviewed-center_reference.json')
REVIEWED_OPPOSING = 'reviewed-opposing_lane.json'
REVIEWED_ONE_WAY = 'reviewed-one_way_authority.json'
CASE_SUFFIXES = ('right_crest_obstructed', 'left_crest_obstructed',
                 'left_crest_clear', 'left_one_way_obstructed')


def _original(attempt: Path, name: str, hashes: dict) -> Path:
    if name not in (*REQUIRED_SOURCES, ONE_WAY_AUTHORITY, PNG_MANIFEST, ROAD_PROFILE,
                    *REVIEWED_COMMON, REVIEWED_OPPOSING, REVIEWED_ONE_WAY) or name not in hashes:
        raise ValueError(f'missing required original source: {name}')
    expected = hashes[name]
    if not isinstance(expected, str) or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError(f'invalid original source hash: {name}')
    path = attempt / name
    if path.is_symlink() or not path.is_file() or path.resolve().parent != attempt.resolve():
        raise ValueError(f'original source path is missing or escapes attempt: {name}')
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f'original source changed: {name}')
    return path


def source_inventory(hashes, case_id, expected_frames):
    required = set(REQUIRED_SOURCES)
    if case_id.endswith('__left_one_way_obstructed'):
        required.add(ONE_WAY_AUTHORITY)
    if expected_frames == 900:
        required.add(PNG_MANIFEST)
        required.add(ROAD_PROFILE)
        required.update(REVIEWED_COMMON)
        required.add(REVIEWED_ONE_WAY if case_id.endswith('__left_one_way_obstructed')
                     else REVIEWED_OPPOSING)
    elif any(name.startswith('reviewed-') for name in hashes):
        required.update(REVIEWED_COMMON)
        required.add(REVIEWED_ONE_WAY if case_id.endswith('__left_one_way_obstructed')
                     else REVIEWED_OPPOSING)
    if expected_frames != 900 and ROAD_PROFILE in hashes:
        required.add(ROAD_PROFILE)
    if not isinstance(hashes, dict) or set(hashes) != required:
        raise ValueError('original source manifest has wrong exact sources')


def audit_original_pngs(attempt, hashes, case_id, frames):
    if PNG_MANIFEST not in hashes:
        return
    manifest = json.loads(_original(attempt, PNG_MANIFEST, hashes).read_text())
    if manifest.get('format') != 'c104084-original-camera-pngs-v1' or manifest.get('case_id') != case_id:
        raise ValueError('original PNG manifest identity differs')
    cameras = manifest.get('frames')
    if not isinstance(cameras, dict) or set(cameras) != {'overview', 'approach', 'reference_corner', 'driver_reference'}:
        raise ValueError('four original PNG archives missing')
    for camera, rows in cameras.items():
        if not isinstance(rows, dict) or set(rows) != {str(frame) for frame in frames}:
            raise ValueError('original PNG frame inventory differs')
        for frame in frames:
            path = attempt / 'original-png' / camera / f'{frame:08d}.png'
            if (path.is_symlink() or not path.is_file() or
                    path.resolve().parent != (attempt / 'original-png' / camera).resolve() or
                    hashlib.sha256(path.read_bytes()).hexdigest() != rows[str(frame)]):
                raise ValueError('original PNG source differs')


def audit_reviewed_sources(attempt, hashes, case_id, context):
    if not any(name.startswith('reviewed-') for name in hashes):
        return
    kinds = ('highway', 'center_reference',
             'one_way_authority' if case_id.endswith('__left_one_way_obstructed')
             else 'opposing_lane')
    refs = {'highway': context.get('highway_source_ref'),
            'center_reference': context.get('center_reference_source_ref'),
            'opposing_lane': context.get('opposing_lane_source_ref'),
            'one_way_authority': context.get('one_way_authority', {}).get('sha256')}
    for kind in kinds:
        name = 'reviewed-' + kind + '.json'
        path = _original(attempt, name, hashes)
        if hashlib.sha256(path.read_bytes()).hexdigest() != refs[kind]:
            raise ValueError('reviewed source and Native context differ: ' + kind)
        document = json.loads(path.read_text())
        if document.get('case_id') != case_id or document.get('source_kind') != kind:
            raise ValueError('reviewed source identity differs: ' + kind)


def _rows(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError('original frame source has no object rows')
    return rows


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(attempt_dir, source_hashes, *, case_id, assignment_id, expected_frames=900):
    """Join Native source packets and return observations with unresolved judgment."""
    if case_id not in {f'{assignment_id}__{suffix}' for suffix in CASE_SUFFIXES}:
        raise ValueError('wrong exact crest case')
    attempt = Path(attempt_dir)
    sources = {name: _original(attempt, name, source_hashes) for name in REQUIRED_SOURCES}
    frames = _rows(sources['frames.jsonl'])
    rays = _rows(sources['crest-rays.jsonl'])
    context = json.loads(sources['lane-context.json'].read_text(encoding='utf-8'))
    frame_map = json.loads(sources['frame-map.json'].read_text(encoding='utf-8'))
    if context.get('case_id') != case_id or context.get('law_id') != 'NRS-484B-213-2a':
        raise ValueError('lane context does not bind exact case and law')
    lane_allocation = context.get('lane_allocation')
    if lane_allocation not in ('two_way', 'one_way'):
        raise ValueError('original lane allocation missing')
    if case_id.endswith('left_one_way_obstructed'):
        authority = context.get('one_way_authority')
        if lane_allocation != 'one_way' or not isinstance(authority, dict) or not authority.get('source_ref') or not re.fullmatch(r'[0-9a-f]{64}', str(authority.get('sha256', ''))):
            raise ValueError('one-way exception lacks original authority binding')
        authority_path = _original(attempt, ONE_WAY_AUTHORITY, source_hashes)
        if hashlib.sha256(authority_path.read_bytes()).hexdigest() != authority['sha256']:
            raise ValueError('one-way authority source hash differs')
    elif lane_allocation != 'two_way' or not context.get('opposing_lane_source_ref'):
        raise ValueError('two-way crest lacks original opposing-lane binding')
    if not context.get('highway_source_ref') or not context.get('center_reference_source_ref'):
        raise ValueError('original highway or center reference missing')
    frame_ids = [row.get('frame') for row in frames]
    ray_ids = [row.get('frame') for row in rays]
    if any(type(value) is not int for value in frame_ids) or frame_ids != list(range(frame_ids[0], frame_ids[0] + len(frame_ids))):
        raise ValueError('original frame history is missing, duplicated or unordered')
    if ray_ids != frame_ids or frame_map.get('frames') != frame_ids:
        raise ValueError('ray or camera frame map does not join original frames')
    if type(expected_frames) is not int or expected_frames <= 0 or len(frame_ids) != expected_frames:
        raise ValueError('original frame history violates required duration')
    source_inventory(source_hashes, case_id, expected_frames)
    audit_reviewed_sources(attempt, source_hashes, case_id, context)
    if ROAD_PROFILE in source_hashes:
        profile = json.loads(_original(attempt, ROAD_PROFILE, source_hashes).read_text())
        blocked = not case_id.endswith('__left_crest_clear')
        if (profile.get('case_id') != case_id or
                profile.get('grade_proxy', {}).get('sampled_grade_blocks_proxy_ray') is not blocked or
                not profile.get('map_opendrive_sha256')):
            raise ValueError('original sampled road profile differs from exact crest case')
    audit_original_pngs(attempt, source_hashes, case_id, frame_ids)
    camera_frames = frame_map.get('camera_frames')
    if not isinstance(camera_frames, dict) or set(camera_frames) != {'overview', 'approach', 'reference_corner', 'driver_reference'}:
        raise ValueError('four-camera frame map missing')
    if any(camera_frames[name] != frame_ids for name in camera_frames):
        raise ValueError('camera frame map has missing or duplicated frames')
    times = [row.get('timestamp_s') for row in frames]
    if any(not _finite(value) for value in times) or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('original timestamps are missing or nonmonotonic')
    if any(abs((b - a) - 0.05) > 0.002 for a, b in zip(times, times[1:])):
        raise ValueError('original frames are not synchronized at 20 Hz')
    left_frames, blocked_frames, clear_frames, distances = [], [], [], []
    for frame, ray in zip(frames, rays):
        corners = frame.get('ego_body_corners_signed_m')
        if not isinstance(corners, list) or len(corners) < 4 or any(not _finite(v) for v in corners):
            raise ValueError('original ego body corners missing')
        distance = frame.get('opposing_body_distance_m')
        if not _finite(distance) or distance < 0:
            raise ValueError('original opposing body distance missing')
        if frame.get('ego_source_ref') is None or frame.get('opposing_source_ref') is None:
            raise ValueError('original actor source identity missing')
        hits = ray.get('body_corner_ray_hits')
        if not isinstance(hits, list) or len(hits) < 4 or any(type(hit) is not bool for hit in hits) or not ray.get('ray_source_ref'):
            raise ValueError('original opposing body rays missing')
        if max(corners) > 0:
            left_frames.append(frame['frame'])
        if all(hits):
            blocked_frames.append(frame['frame'])
        if not any(hits):
            clear_frames.append(frame['frame'])
        distances.append(distance)
    suffix = case_id[len(assignment_id) + 2:]
    expected_left = suffix != 'right_crest_obstructed'
    expected_blocked = suffix != 'left_crest_clear'
    # A left-side and obstruction observation must describe the same original
    # frame. Separate episodes cannot establish the intended crest condition.
    target_frames = blocked_frames if expected_blocked else clear_frames
    coincident_frames = sorted(set(left_frames if expected_left else frame_ids)
                               & set(target_frames))
    target_observed = (bool(left_frames) == expected_left and
                       bool(coincident_frames) and
                       (expected_blocked or not blocked_frames))
    return {
        'case_id': case_id,
        'source_sha256': {name: source_hashes[name] for name in
                          (*REQUIRED_SOURCES,
                           *([ONE_WAY_AUTHORITY] if lane_allocation == 'one_way' else []),
                           *([PNG_MANIFEST] if PNG_MANIFEST in source_hashes else []),
                           *([ROAD_PROFILE] if ROAD_PROFILE in source_hashes else []),
                           *(name for name in source_hashes if name.startswith('reviewed-')))},
        'frame_count': len(frames),
        'first_frame': frame_ids[0],
        'last_frame': frame_ids[-1],
        'lane_allocation': lane_allocation,
        'ego_body_left_side_frames': left_frames,
        'opposing_body_distance_m': {'minimum': min(distances), 'maximum': max(distances)},
        'all_corner_rays_blocked_frames': blocked_frames,
        'all_corner_rays_clear_frames': clear_frames,
        'body_and_view_target_frames': coincident_frames,
        'construction_target_observed': target_observed,
        'hazard_distance_judgment': 'unresolved',
        'limitations': 'Signed body corners and Native ray packets are observations. Neither sampled geometry nor video filenames establish actual driver perception, public highway law, or a legal hazard distance.',
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--source-hashes', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--assignment', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    hashes = json.loads(Path(args.source_hashes).read_text(encoding='utf-8'))
    result = measure(args.attempt, hashes, case_id=args.case, assignment_id=args.assignment)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
