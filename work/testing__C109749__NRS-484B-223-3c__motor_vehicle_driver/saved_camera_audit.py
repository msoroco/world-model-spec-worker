"""Independent full decode of saved original four-camera PNG frame sources."""

import hashlib
import json
from pathlib import Path

from PIL import Image


DIMENSIONS = {'overview': (1920, 1080), 'approach': (1280, 720),
              'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def audit_original_pngs(attempt_root, frame_map_binding, expected_frames, dimensions=None):
    root = Path(attempt_root).resolve()
    expected = DIMENSIONS if dimensions is None else dimensions
    if not isinstance(expected, dict) or set(expected) != set(DIMENSIONS):
        raise ValueError('incomplete expected four-camera dimensions')
    if not isinstance(frame_map_binding, dict) or frame_map_binding.get('path') != 'native/frame_map.json':
        raise ValueError('missing fixed original frame map binding')
    path = root / 'native/frame_map.json'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != frame_map_binding.get('sha256'):
        raise ValueError('original frame map hash mismatch')
    frame_map = json.loads(raw.decode('utf-8'))
    rows = frame_map.get('frames')
    if frame_map.get('fps') != 20 or not isinstance(rows, list) or len(rows) != expected_frames:
        raise ValueError('incomplete original 20 Hz frame map')
    seen = set()
    previous = None
    decoded = 0
    for row in rows:
        frame = row.get('frame')
        if type(frame) is not int or (previous is not None and frame != previous + 1):
            raise ValueError('noncontiguous original camera frame')
        previous = frame
        sources = row.get('camera_sources')
        hashes = row.get('camera_sha256')
        if not isinstance(sources, dict) or not isinstance(hashes, dict) or set(sources) != set(expected) or set(hashes) != set(expected):
            raise ValueError('incomplete original four-camera source map')
        for view in expected:
            relative = sources[view]
            if relative != 'camera/' + view + '/%06d.png' % frame or relative in seen:
                raise ValueError('substituted or duplicate original camera path')
            seen.add(relative)
            source = (root / relative).resolve()
            if not source.is_relative_to(root) or not source.is_file():
                raise ValueError('missing original camera source')
            if hashlib.sha256(source.read_bytes()).hexdigest() != hashes[view]:
                raise ValueError('original camera source hash mismatch')
            with Image.open(source) as image:
                image.load()
                if image.format != 'PNG' or image.mode != 'RGB' or image.size != tuple(expected[view]):
                    raise ValueError('original camera PNG profile mismatch: ' + view)
            decoded += 1
    return {'frame_count': len(rows), 'decoded_camera_images': decoded,
            'frame_map_sha256': frame_map_binding['sha256'], 'physical_acceptance': None}
