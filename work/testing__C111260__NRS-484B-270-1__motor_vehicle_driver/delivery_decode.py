"""Saved-only full camera decode for the bicycle encounter.

This establishes that each sealed stream decodes at the declared frame count.
It does not establish that a rider is visible or that the encounter is lawful.
"""
from __future__ import annotations

import hashlib
import subprocess

from bicycle_encounter import read_source, require
from saved_attempt import FPS, VIEWS, finalize, probe_video


def decode_camera(path, expected_frames):
    """Decode all video frames through FFmpeg's per-frame hash muxer."""
    command = ['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:v:0',
               '-an', '-f', 'framemd5', '-']
    result = subprocess.run(command, capture_output=True, check=False)
    require(result.returncode == 0, 'full camera decode failed')
    lines = [line for line in result.stdout.splitlines() if line and not line.startswith(b'#')]
    require(len(lines) == expected_frames, 'full camera decoded frame count mismatch')
    require(all(len(line.split(b',')) == 6 for line in lines),
            'full camera frame hash line malformed')
    return hashlib.sha256(result.stdout).hexdigest()


def audit(root, camera_sources, expected_frames, decoder=decode_camera):
    """Audit four distinct sealed sources and return compact decode receipts."""
    require(set(camera_sources) == set(VIEWS), 'four exact camera sources required')
    paths = {view: read_source(camera_sources[view], root) for view in VIEWS}
    require(len(set(paths.values())) == len(VIEWS), 'camera sources must be distinct')
    receipts = {}
    for view, path in paths.items():
        meta = probe_video(path)
        require(meta['fps'] == FPS and meta['frame_count'] == expected_frames,
                'camera frame rate or duration mismatch: ' + view)
        frame_hash = decoder(path, expected_frames)
        require(isinstance(frame_hash, str) and len(frame_hash) == 64,
                'full camera frame hash missing')
        read_source(camera_sources[view], root)
        receipts[view] = {
            'source_sha256': camera_sources[view]['sha256'],
            'frame_count': expected_frames,
            'fps': FPS,
            'width': meta['width'],
            'height': meta['height'],
            'framemd5_sha256': frame_hash,
        }
    return {'full_video_decode': True, 'pixel_visibility_verified': False,
            'camera_decode_receipts': receipts}


def finalize_delivery(site, root, event_ref, camera_sources, mode, frames):
    """Join saved event measurement to independent full camera decoding."""
    measurement = finalize(site, root, event_ref, camera_sources, mode,
                           probe_video, frames=frames)
    decoded = audit(root, camera_sources, frames)
    for view in VIEWS:
        receipt = decoded['camera_decode_receipts'][view]
        require(all(receipt[key] == measurement['camera_metadata'][view][key]
                    for key in ('frame_count', 'fps', 'width', 'height')),
                'decoded stream differs from measured stream')
    measurement.update(decoded)
    return measurement
