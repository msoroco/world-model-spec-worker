"""Independent full decode of original four-camera parking-device media.

The input is a sealed attempt with Native frame rows and four PNG archives.
This is a software integrity check; it makes no claim about sign legibility.
"""
from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image


CAMERAS = ('front', 'rear', 'left', 'right')
PROFILE_DIMENSIONS = {'front': [1920, 1080], 'rear': [1280, 720],
                      'left': [1280, 720], 'right': [1280, 720]}


def _source(root, ref):
    path = (root / ref['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('original source path missing or escapes attempt')
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
        raise ValueError('original source hash mismatch')
    return path


def audit_media(attempt, attempt_root, expected_dimensions=None):
    """Check every saved PNG byte binding, decode and Native frame join."""
    root = Path(attempt_root).resolve()
    profile = PROFILE_DIMENSIONS if expected_dimensions is None else expected_dimensions
    if attempt.get('source_format') != 'native_original' or attempt.get('fps') != 20:
        raise ValueError('original 20 Hz capture required')
    rows = json.loads(_source(root, attempt['actor_rows']).read_text())
    frame_map = json.loads(_source(root, attempt['frame_map']).read_text())
    n = attempt['frame_count']
    if n != 900 or len(rows) != n or len(frame_map) != n:
        raise ValueError('original 900-frame capture incomplete')
    if set(attempt.get('camera_archives', {})) != set(CAMERAS):
        raise ValueError('four original camera archives required')
    frames = [attempt['first_frame'] + i for i in range(n)]
    for i, frame in enumerate(frames):
        if rows[i].get('frame') != frame or frame_map[i].get('frame') != frame:
            raise ValueError('Native frame map mismatch')
        if rows[i].get('time_s') != frame_map[i].get('time_s'):
            raise ValueError('Native frame time mismatch')
        if i and abs(rows[i]['time_s'] - rows[i-1]['time_s'] - 0.05) > 0.001:
            raise ValueError('Native frame cadence mismatch')
    for camera in CAMERAS:
        ref = attempt['camera_archives'][camera]
        if ref.get('frame_count') != n or ref.get('fps') != 20:
            raise ValueError(f'{camera} camera profile mismatch')
        dims = ref.get('dimensions')
        if dims != profile[camera]:
            raise ValueError(f'{camera} camera profile dimensions mismatch')
        path = _source(root, ref)
        expected_members = [f'{frame:08d}.png' for frame in frames]
        with ZipFile(path) as archive:
            if archive.namelist() != expected_members:
                raise ValueError(f'{camera} original frame sequence mismatch')
            for row, member in zip(rows, expected_members):
                payload = archive.read(member)
                binding = row.get('camera_frames', {}).get(camera)
                if binding != {'member': member, 'sha256': hashlib.sha256(payload).hexdigest()}:
                    raise ValueError(f'{camera} original pixel binding mismatch')
                with Image.open(BytesIO(payload)) as image:
                    image.verify()
                with Image.open(BytesIO(payload)) as image:
                    if image.format != 'PNG' or list(image.size) != dims:
                        raise ValueError(f'{camera} original PNG dimensions mismatch')
                    image.load()
    return {'format': 'parking-device-original-media-audit', 'case_id': attempt['case_id'],
            'source_frame_count': n, 'decoded_images': n * len(CAMERAS),
            'original_camera_hashes': {name: attempt['camera_archives'][name]['sha256'] for name in CAMERAS},
            'physical_acceptance': False, 'legal_judgment': None}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--capture-root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    attempt = json.loads(Path(args.attempt).read_text())
    result = audit_media(attempt, args.capture_root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
