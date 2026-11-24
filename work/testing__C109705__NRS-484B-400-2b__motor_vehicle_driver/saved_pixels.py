"""Decode every source-bound original PNG frame for a four-camera attempt."""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image, UnidentifiedImageError

CAMERAS = ('dash', 'front', 'left', 'right')
DELIVERY_SIZE = {'dash': (1920, 1080), 'front': (1280, 720),
                 'left': (1280, 720), 'right': (1280, 720)}


def decode(root, index, frames, *, delivery=False):
    """Require one distinct, complete PNG per channel and original Native tick.

    Hashes are checked against the camera index before full Pillow decoding.
    A diagnostic may use a small image size; delivery uses the capture profile.
    """
    root = Path(root).resolve()
    if set(index.get('channels', {})) != set(CAMERAS) or len(frames) != 900:
        raise ValueError('four-camera 900-frame PNG index required')
    dimensions = {}
    counts = {}
    for channel in CAMERAS:
        rows = index['channels'][channel]
        if not isinstance(rows, list) or len(rows) != 900:
            raise ValueError('900 original PNG frames required per channel')
        seen = set()
        for frame, row in zip(frames, rows):
            if row.get('frame') != frame or row.get('channel') != channel:
                raise ValueError('PNG frame/time/channel join differs')
            relative = row.get('source_path')
            if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or any(
                    part in ('.', '..') for part in Path(relative).parts):
                raise ValueError('PNG source path escapes attempt')
            path = (root / relative).resolve()
            if not path.is_relative_to(root) or path.suffix.lower() != '.png' or not path.is_file():
                raise ValueError('original PNG source missing')
            if path in seen:
                raise ValueError('PNG source reused for multiple frames')
            seen.add(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != row.get('source_sha256'):
                raise ValueError('original PNG source hash differs')
            try:
                with Image.open(path) as im:
                    if im.format != 'PNG' or im.mode not in ('RGB', 'RGBA'):
                        raise ValueError('original PNG format or color mode differs')
                    size = im.size
                    im.load()
            except (UnidentifiedImageError, OSError) as exc:
                raise ValueError('original PNG full decode failed') from exc
            if channel in dimensions and dimensions[channel] != size:
                raise ValueError('original PNG dimensions vary within channel')
            if delivery and size != DELIVERY_SIZE[channel]:
                raise ValueError('original PNG capture profile dimensions differ')
            dimensions[channel] = size
        counts[channel] = len(seen)
    return {'full_source_decode': True, 'decoded_frames': counts,
            'source_dimensions_px': {k: list(v) for k, v in dimensions.items()},
            'actual_pixels': True, 'visible_participants_verified': False}
