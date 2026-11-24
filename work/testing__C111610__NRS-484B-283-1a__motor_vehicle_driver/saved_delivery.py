"""Join independently checked saved measurements and original camera evidence.

This is a CPU source-consistency receipt, not a physical or legal acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from saved_measurement import process
from saved_media_audit import audit


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def join(attempt, scene_path, output, *, dimensions=None):
    attempt, scene_path, output = Path(attempt), Path(scene_path), Path(output)
    measurement_path = output.parent / (output.stem + '-measurement.json')
    measurement = process(attempt, scene_path, measurement_path)
    media = audit(attempt, scene_path, dimensions=dimensions)
    frame_map = json.loads((attempt / 'frame_map.json').read_text(encoding='utf-8'))
    ego = json.loads((attempt / 'ego.json').read_text(encoding='utf-8'))
    pedestrian = json.loads((attempt / 'pedestrian.json').read_text(encoding='utf-8'))
    if not (len(frame_map) == len(ego) == len(pedestrian) == measurement['frame_count'] ==
            media['frames'] == 600):
        raise ValueError('saved actor/camera frame count mismatch')
    for i, (frame, driver, person) in enumerate(zip(frame_map, ego, pedestrian)):
        for actor in (driver, person):
            if any(actor.get(key) != frame.get(key) for key in
                   ('frame', 'elapsed_s', 'native_frame', 'native_elapsed_s')):
                raise ValueError(f'original actor/camera frame-time join mismatch at {i}')
    if (measurement['case_id'] != media['case_id'] or
            measurement['scene_sha256'] != media['scene_sha256'] or
            measurement['source_index_sha256'] != media['source_index_sha256']):
        raise ValueError('saved actor/camera source identity mismatch')
    receipt = {
        'format': 'c111610-saved-delivery-join-v1',
        'case_id': measurement['case_id'],
        'scene_sha256': measurement['scene_sha256'],
        'source_index_sha256': measurement['source_index_sha256'],
        'measurement_sha256': _sha(measurement_path),
        'camera_manifest_sha256': media['camera_manifest_sha256'],
        'frame_map_sha256': media['frame_map_sha256'],
        'joined_frames': 600,
        'decoded_view_frames': media['decoded_view_frames'],
        'actor_camera_clock_join': 'verified',
        'physical_source_verified': False,
        'pixel_visibility': 'unreviewed',
        'legal_judgment': 'unresolved',
    }
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return receipt
