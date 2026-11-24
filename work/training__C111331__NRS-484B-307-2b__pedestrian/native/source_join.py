"""Reject missing original-camera joins before entry measurement.

This verifies provenance structure and hash joins. It cannot verify that a
particular pixel depicts a circular green or a governing pedestrian device.
"""

import hashlib
import json
from pathlib import Path

from construction import VIEWS


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def join(native_path, frame_map_path, rgb_dir=None):
    native = _rows(native_path)
    mapping = _rows(frame_map_path)
    if len(native) != 600 or len(mapping) != 600:
        raise ValueError('600 original Native and frame-map rows required')
    rgb_dir = Path(rgb_dir) if rgb_dir is not None else None
    seen = set()
    for index, (sample, frame) in enumerate(zip(native, mapping)):
        if sample.get('video_frame') != index or frame.get('video_frame') != index:
            raise ValueError('Video frame sequence differs')
        if sample.get('native_frame') != frame.get('native_frame') or \
                sample.get('native_frame') in seen:
            raise ValueError('Native frame identity join differs')
        seen.add(sample['native_frame'])
        if abs(sample.get('time_s', -1) - frame.get('time_s', -2)) > 1e-6:
            raise ValueError('Native and video frame time join differs')
        pixels = frame.get('source_rgb_sha256')
        if not isinstance(pixels, dict) or set(pixels) != {name for name, _, _ in VIEWS}:
            raise ValueError('Four original camera hashes missing')
        for name, width, height in VIEWS:
            digest = pixels[name]
            if not isinstance(digest, str) or len(digest) != 64 or \
                    any(c not in '0123456789abcdef' for c in digest):
                raise ValueError(f'Original RGB digest missing: {name} frame {index}')
            if rgb_dir is not None:
                rgb = rgb_dir / name / f'{index:06d}.rgb'
                if not rgb.is_file() or rgb.stat().st_size != width * height * 3:
                    raise ValueError(f'Original RGB dimensions missing: {name} frame {index}')
                if hashlib.sha256(rgb.read_bytes()).hexdigest() != digest:
                    raise ValueError(f'Original RGB hash differs: {name} frame {index}')
        if sample.get('pedestrian_id') is None or \
                not isinstance(sample.get('pedestrian_xy_m'), list) or \
                len(sample['pedestrian_xy_m']) != 2:
            raise ValueError('Original Native pedestrian pose missing')
        if sample.get('traffic_head_id') is None or sample.get('pedestrian_head_id') is None:
            raise ValueError('Native device identity samples missing')
    return {'format': 'c111331-original-source-join-v1', 'frames': 600,
            'cameras': [name for name, _, _ in VIEWS],
            'native_source_joined': True, 'source_rgb_bytes_verified': rgb_dir is not None,
            'actual_indication_pixels_reviewed': False,
            'device_governance_reviewed': False, 'legal_verdict': None}
