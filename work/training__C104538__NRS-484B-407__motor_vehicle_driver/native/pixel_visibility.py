"""Synthetic marker visibility threshold diagnostic; no original-pixel verdict."""
import hashlib
import json
from pathlib import Path


def measure(source):
    source = Path(source)
    manifest = json.loads((source / 'pixel-manifest.json').read_text())
    if manifest.get('format') != 'c104538-pixel-source-v1':
        raise ValueError('Unknown camera pixel source')
    if manifest.get('source_kind') != 'synthetic_cpu_fixture':
        raise ValueError('Synthetic marker detector cannot audit original pixels')
    width, height, frames = (manifest.get(key) for key in ('width', 'height', 'frames'))
    if (width, height, frames) != (32, 32, 480):
        raise ValueError('Camera source dimensions or duration differ')
    frame_size = width * height * 3
    result = {}
    for role in ('reference_left', 'reference_right'):
        rows = [json.loads(line) for line in (source / (role + '.jsonl')).read_text().splitlines()]
        data = (source / (role + '.rgb')).read_bytes()
        if len(rows) != frames or len(data) != frames * frame_size:
            raise ValueError('Camera source frame count differs')
        seen = 0
        for index, row in enumerate(rows):
            rgb = data[index * frame_size:(index + 1) * frame_size]
            if row.get('frame') != index or row.get('camera') != role:
                raise ValueError('Camera source frame identity differs')
            if hashlib.sha256(rgb).hexdigest() != row.get('rgb_sha256'):
                raise ValueError('Camera source RGB hash differs')
            pixels = [rgb[j:j + 3] for j in range(0, len(rgb), 3)]
            body = sum(pixel == b'\xff\x00\x00' for pixel in pixels)
            centerline = sum(pixel == b'\xff\xff\xff' for pixel in pixels)
            seen += body >= 12 and centerline >= 16
        result[role] = {'visible_frames': seen, 'fraction': seen / frames}
    return {'format': 'c104538-camera-trigger-measurement-v1',
            'source_kind': manifest['source_kind'], 'frames': frames,
            'camera_visibility': result,
            'fallback3_trigger_measured': any(value['fraction'] < .95 for value in result.values()),
            'original_pixel_observed': False,
            'legal_verdict_claimed': False, 'accepted': False}
