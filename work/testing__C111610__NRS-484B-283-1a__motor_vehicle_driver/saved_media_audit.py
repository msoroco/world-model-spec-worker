"""Independently decode and hash all four original cameras for one saved attempt."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from PIL import Image

from native_capture import CAMERAS, DIMENSIONS


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def audit(attempt, scene_path, *, dimensions=None):
    attempt, scene_path = Path(attempt), Path(scene_path)
    index = json.loads((attempt / 'source-index.json').read_text())
    scene = json.loads(scene_path.read_text())
    if (index.get('format') != 'c111610-native-source-index-v1' or
        index.get('case_id') != scene.get('case_id') or
        index.get('scene_sha256') != _sha(scene_path.read_bytes()) or
        index.get('physical_acceptance_claimed') is not False):
        raise ValueError('original attempt/scene source seal mismatch')
    files = index.get('files', {})
    required = ('site', 'ego', 'pedestrian', 'exception_review', 'frame_map', 'camera_manifest')
    if set(files) != set(required):
        raise ValueError('original source index incomplete')
    for name, entry in files.items():
        path = Path(entry.get('path', ''))
        if path.name != name + '.json' or len(path.parts) != 1 or entry.get('source') != 'native_original':
            raise ValueError('source index path or provenance invalid')
        if _sha((attempt / path).read_bytes()) != entry.get('sha256'):
            raise ValueError('original source file hash mismatch')
    rows = json.loads((attempt / 'camera_manifest.json').read_text())
    frames = json.loads((attempt / 'frame_map.json').read_text())
    if len(rows) != 600 or len(frames) != 600:
        raise ValueError('complete 600-frame camera and original frame map required')
    dims = DIMENSIONS if dimensions is None else dimensions
    if set(dims) != set(CAMERAS):
        raise ValueError('all four camera dimensions required')
    hashes = {name: hashlib.sha256() for name in CAMERAS}
    previous_native = None
    for i, (row, frame) in enumerate(zip(rows, frames)):
        for entry in (row, frame):
            if (entry.get('frame') != i or abs(entry.get('elapsed_s', -1) - i / 20) > .001 or
                entry.get('native_frame') != row.get('native_frame') or
                abs(entry.get('native_elapsed_s', -1) - row.get('native_elapsed_s', -2)) > .001):
                raise ValueError('camera/original frame-time join mismatch')
        if previous_native is not None and row['native_frame'] != previous_native + 1:
            raise ValueError('original Native frame gap')
        previous_native = row['native_frame']
        if set(row.get('views', {})) != set(CAMERAS):
            raise ValueError('four original camera views required')
        for name in CAMERAS:
            item = row['views'][name]
            relative = Path(item.get('path', ''))
            if (relative.parts != ('original-frames', f'{name}-{i:06d}.png') or
                relative.is_absolute()):
                raise ValueError('original camera frame path invalid')
            data = (attempt / relative).read_bytes()
            if _sha(data) != item.get('sha256'):
                raise ValueError('original camera bytes changed')
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                if image.format != 'PNG' or image.size != tuple(dims[name]) or image.mode not in ('RGB', 'RGBA'):
                    raise ValueError('original camera decode/profile mismatch')
            hashes[name].update(data)
    return {'format': 'c111610-saved-media-audit', 'case_id': scene['case_id'],
            'scene_sha256': _sha(scene_path.read_bytes()),
            'source_index_sha256': _sha((attempt / 'source-index.json').read_bytes()),
            'camera_manifest_sha256': _sha((attempt / 'camera_manifest.json').read_bytes()),
            'frame_map_sha256': _sha((attempt / 'frame_map.json').read_bytes()),
            'frames': 600, 'rate_hz': 20, 'views': list(CAMERAS),
            'decoded_view_frames': 2400,
            'view_stream_sha256': {name: digest.hexdigest() for name, digest in hashes.items()},
            'pixel_visibility': 'unreviewed', 'physical_acceptance': False,
            'legal_judgment': None}
