"""Lazy Native capture orchestration for the four exact crest cases.

The adapter owns CARLA world/sensor creation. This module enforces a source join,
20 Hz duration, camera callback completeness, and guaranteed adapter cleanup.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

try:
    from saved_crest import CASE_SUFFIXES
except ImportError:  # package loading in tests
    CASE_SUFFIXES = ('right_crest_obstructed', 'left_crest_obstructed',
                     'left_crest_clear', 'left_one_way_obstructed')

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
ONE_WAY_AUTHORITY = 'one-way-authority.json'


def _write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')


def capture(adapter, output_dir, *, assignment_id, case_id, frames=900,
            graph_observer=None):
    """Acquire original packets through a caller-supplied CARLA adapter.

    Adapter contract: begin(case), tick(), sample(frame), camera_frames(frame),
    write_camera_video(camera,path), close(). begin returns source-bound lane
    context including highway and opposite/one-way authority references. sample
    returns body history and ray packet. camera_frames returns frame IDs received
    from each original camera callback; this API does not make pixels itself.
    """
    if case_id not in {f'{assignment_id}__{suffix}' for suffix in CASE_SUFFIXES}:
        raise ValueError('wrong exact crest case')
    if type(frames) is not int or frames <= 0:
        raise ValueError('invalid capture duration')
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('retain prior attempt; choose a fresh empty output directory')
    history, rays = [], []
    camera_map = {name: [] for name in CAMERAS}
    try:
        context = adapter.begin(case_id)
        if not isinstance(context, dict) or context.get('case_id') != case_id:
            raise ValueError('original lane context does not bind exact case')
        if context.get('law_id') != 'NRS-484B-213-2a':
            raise ValueError('original lane context has wrong law')
        if not context.get('highway_source_ref') or not context.get('center_reference_source_ref'):
            raise ValueError('original highway or center reference absent')
        if case_id.endswith('left_one_way_obstructed'):
            authority = context.get('one_way_authority')
            if (context.get('lane_allocation') != 'one_way' or not isinstance(authority, dict)
                    or not authority.get('source_ref') or not authority.get('sha256')):
                raise ValueError('one-way authority source absent')
            authority_file = output / ONE_WAY_AUTHORITY
            if (authority_file.is_symlink() or not authority_file.is_file() or
                    hashlib.sha256(authority_file.read_bytes()).hexdigest() != authority['sha256']):
                raise ValueError('one-way authority source file differs')
        elif context.get('lane_allocation') != 'two_way' or not context.get('opposing_lane_source_ref'):
            raise ValueError('opposing lane source absent')
        last_time = None
        for offset in range(frames):
            frame = adapter.tick()
            if type(frame) is not int or (history and frame != history[-1]['frame'] + 1):
                raise ValueError('Native world frames are missing or unordered')
            body, ray = adapter.sample(frame)
            if not isinstance(body, dict) or not isinstance(ray, dict):
                raise ValueError('original Native actor or ray packet missing')
            if body.get('frame') != frame or ray.get('frame') != frame:
                raise ValueError('Native body/ray frame join mismatch')
            timestamp = body.get('timestamp_s')
            if type(timestamp) not in (int, float) or not math.isfinite(timestamp):
                raise ValueError('Native timestamp missing')
            if last_time is not None and abs(timestamp - last_time - 0.05) > 0.002:
                raise ValueError('Native world is not synchronized at 20 Hz')
            last_time = timestamp
            if graph_observer is not None:
                graph_observer(frame, timestamp)
            callbacks = adapter.camera_frames(frame)
            if not isinstance(callbacks, dict) or set(callbacks) != set(CAMERAS):
                raise ValueError('four original camera callbacks missing')
            if any(callbacks[name] != frame for name in CAMERAS):
                raise ValueError('camera callback frame join mismatch')
            for name in CAMERAS:
                camera_map[name].append(frame)
            history.append(body)
            rays.append(ray)
        _write_json(output / 'lane-context.json', context)
        _write_json(output / 'frame-map.json', {'frames': [row['frame'] for row in history],
                                                'camera_frames': camera_map})
        for name, rows in (('frames.jsonl', history), ('crest-rays.jsonl', rays)):
            (output / name).write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                               for row in rows), encoding='utf-8')
        for camera in CAMERAS:
            path = output / f'{camera}.mkv'
            adapter.write_camera_video(camera, path)
            if not path.is_file() or not path.stat().st_size:
                raise ValueError(f'original camera video missing: {camera}')
        names = ('frames.jsonl', 'crest-rays.jsonl', 'lane-context.json',
                 'frame-map.json', *(f'{name}.mkv' for name in CAMERAS),
                 *([ONE_WAY_AUTHORITY] if case_id.endswith('left_one_way_obstructed') else []),
                 *(f'reviewed-{name}.json' for name in
                   ('highway', 'center_reference',
                    'one_way_authority' if case_id.endswith('left_one_way_obstructed')
                    else 'opposing_lane') if
                   (output / f'reviewed-{name}.json').is_file()),
                 *(['original-png-manifest.json'] if
                   (output / 'original-png-manifest.json').is_file() else []),
                 *(['road-profile.json'] if
                   (output / 'road-profile.json').is_file() else []))
        hashes = {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                  for name in names}
        _write_json(output / 'source-hashes.json', hashes)
        return {'case_id': case_id, 'frame_count': frames, 'source_sha256': hashes,
                'physical_visibility_reviewed': False}
    finally:
        adapter.close()
