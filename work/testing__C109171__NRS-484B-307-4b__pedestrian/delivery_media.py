"""Independent saved delivery audit for the four original pedestrian views.

This verifies source identity, timing and pinned image dimensions. Pixel visibility
and the statutory permission of a separate device still require review.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from PIL import Image

from native_capture import CAMERAS, DEFAULT_FRAMES, audit_frame_map
from native_scene import SourceError

PROFILE_SIZES = {
    'overview': (1920, 1080),
    'approach': (1280, 720),
    'reference_corner': (1280, 720),
    'driver_reference': (1280, 720),
}


def audit_delivery_media(attempt, frame_map_ref, events_ref,
                         expected_frames=DEFAULT_FRAMES):
    """Reopen every original PNG and require its exact pinned view dimensions."""
    base = Path(attempt).resolve(strict=True)
    if set(CAMERAS) != set(PROFILE_SIZES):
        raise SourceError('pinned delivery camera profile incomplete')
    source_audit = audit_frame_map(base, frame_map_ref, events_ref, expected_frames)
    map_path = (base / frame_map_ref['path']).resolve(strict=True)
    if not map_path.is_relative_to(base) or hashlib.sha256(map_path.read_bytes()).hexdigest() != frame_map_ref['sha256']:
        raise SourceError('original frame map changed')
    rows = json.loads(map_path.read_text(encoding='utf-8'))
    for row in rows:
        for camera in CAMERAS:
            ref = row['cameras'][camera]
            path = (base / ref['path']).resolve(strict=True)
            if not path.is_relative_to(base):
                raise SourceError('original camera path outside attempt')
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != ref['sha256']:
                raise SourceError('original camera hash changed')
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != 'PNG' or image.size != PROFILE_SIZES[camera]:
                    raise SourceError('original camera dimensions differ from pinned profile: ' + camera)
                image.load()
    return {'frame_count': expected_frames,
            'decoded_source_frames': source_audit['camera_frames_audited'],
            'pinned_dimensions_verified': True,
            'frame_map_sha256': frame_map_ref['sha256'],
            'events_sha256': events_ref['sha256'],
            'physical_visibility': 'unreviewed',
            'statutory_permission': 'unresolved'}
