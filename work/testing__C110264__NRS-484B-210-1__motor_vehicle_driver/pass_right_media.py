"""Independent full decode of original four-camera PNG archives.

An archive contains one lossless PNG named ``000000.png`` through
``000899.png``. These are source frames, not a composed presentation video.
The caller must separately establish the Native frame map and physical view.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from PIL import Image

PROFILE = {'front': (1920, 1080), 'rear': (1280, 720),
           'left': (1280, 720), 'right': (1280, 720)}
FRAME_COUNT = 900


def audit_archive(path: Path, expected_size: tuple[int, int],
                  expected_frames: int = FRAME_COUNT) -> dict:
    """Read every PNG and reject missing, repeated, damaged, or wrong-size frames."""
    if expected_frames < 1 or min(expected_size) < 1:
        raise ValueError('positive media profile required')
    try:
        with ZipFile(path) as archive:
            entries = archive.infolist()
            expected_names = [f'{index:06d}.png' for index in range(expected_frames)]
            names = [entry.filename for entry in entries]
            if names != expected_names or any(entry.is_dir() for entry in entries):
                raise ValueError('camera archive frame order/count mismatch')
            pixel_hash = hashlib.sha256()
            for index, entry in enumerate(entries):
                if entry.file_size > 32 * 1024 * 1024:
                    raise ValueError('camera frame exceeds decode limit')
                data = archive.read(entry)
                try:
                    with Image.open(io.BytesIO(data)) as image:
                        if image.format != 'PNG' or image.size != expected_size:
                            raise ValueError('camera PNG format or dimensions mismatch')
                        image.load()
                        pixel_hash.update(index.to_bytes(4, 'big'))
                        pixel_hash.update(image.convert('RGB').tobytes())
                except (OSError, SyntaxError) as exc:
                    raise ValueError('camera PNG full decode failed') from exc
    except BadZipFile as exc:
        raise ValueError('camera archive is not a readable ZIP') from exc
    return {'frame_count': expected_frames, 'dimensions': list(expected_size),
            'full_pixel_sha256': pixel_hash.hexdigest(), 'format': 'png-zip-source'}


def audit_cameras(root: Path, cameras: dict, profile: dict | None = None,
                  expected_frames: int = FRAME_COUNT) -> dict:
    """Verify all original archive hashes, then decode against the fixed profile."""
    sizes = PROFILE if profile is None else profile
    if not isinstance(sizes, dict) or set(sizes) != set(PROFILE):
        raise ValueError('incomplete camera dimension profile')
    if not isinstance(cameras, dict) or set(cameras) != set(PROFILE):
        raise ValueError('all four original camera archives required')
    result = {}
    for name, dimensions in sizes.items():
        source = cameras[name]
        if not isinstance(source, dict) or set(source) != {'path', 'sha256'}:
            raise ValueError(name + ' camera source path and sha256 required')
        path = (root / source['path']).resolve()
        if root.resolve() not in path.parents or not path.is_file():
            raise ValueError(name + ' camera source outside attempt or missing')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != source['sha256']:
            raise ValueError(name + ' camera archive sha256 mismatch')
        result[name] = {'source_sha256': source['sha256'],
                        **audit_archive(path, dimensions, expected_frames)}
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    result = audit_cameras(args.attempt, manifest.get('cameras'))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
