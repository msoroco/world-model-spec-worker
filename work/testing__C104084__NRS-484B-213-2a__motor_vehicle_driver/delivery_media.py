"""Independent source-bound four-camera full-decode check for saved Native attempts.

This is a CPU delivery guard, not proof that an actor or crest is visible.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from fractions import Fraction
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _run(command):
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        raise ValueError(f'media decode failed: {result.stderr[-600:]}')
    return result.stdout


def audit(attempt_dir, source_hashes, *, expected_frames=900, expected_fps=20,
          expected_dimensions=None):
    """Reopen exact originals, count and decode every frame of every camera."""
    attempt = Path(attempt_dir).resolve()
    if type(expected_frames) is not int or expected_frames <= 0:
        raise ValueError('invalid required frame count')
    if type(expected_fps) is not int or expected_fps <= 0:
        raise ValueError('invalid required frame rate')
    if expected_dimensions is not None and (not isinstance(expected_dimensions, dict)
            or set(expected_dimensions) != set(CAMERAS)):
        raise ValueError('incomplete camera dimension plan')
    receipts = {}
    for camera in CAMERAS:
        name = f'{camera}.mkv'
        expected_hash = source_hashes.get(name)
        if not isinstance(expected_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_hash):
            raise ValueError(f'camera source hash missing: {name}')
        source = attempt / name
        if source.is_symlink() or not source.is_file() or source.resolve().parent != attempt:
            raise ValueError(f'camera original missing or escapes attempt: {name}')
        actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f'camera original changed: {name}')
        probe = json.loads(_run(['ffprobe', '-v', 'error', '-count_frames',
                                 '-select_streams', 'v:0', '-show_entries',
                                 'stream=codec_name,width,height,r_frame_rate,nb_read_frames',
                                 '-of', 'json', str(source)]))
        streams = probe.get('streams') or []
        if len(streams) != 1:
            raise ValueError(f'camera video stream missing: {name}')
        stream = streams[0]
        if Fraction(stream.get('r_frame_rate', '0/1')) != expected_fps:
            raise ValueError(f'camera frame rate mismatch: {name}')
        if int(stream.get('nb_read_frames', -1)) != expected_frames:
            raise ValueError(f'camera frame count mismatch: {name}')
        width, height = stream.get('width'), stream.get('height')
        if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
            raise ValueError(f'camera dimensions missing: {name}')
        if expected_dimensions is not None and (width, height) != tuple(expected_dimensions[camera]):
            raise ValueError(f'camera dimensions mismatch: {name}')
        frame_probe = json.loads(_run(['ffprobe', '-v', 'error',
                                       '-select_streams', 'v:0',
                                       '-show_entries', 'frame=best_effort_timestamp_time',
                                       '-of', 'json', str(source)]))
        frames = frame_probe.get('frames')
        if not isinstance(frames, list) or len(frames) != expected_frames:
            raise ValueError(f'camera presentation frame count mismatch: {name}')
        for index, frame in enumerate(frames):
            try:
                presentation = float(frame['best_effort_timestamp_time'])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f'camera presentation timestamp missing: {name}') from error
            if not math.isfinite(presentation) or abs(presentation - index / expected_fps) > 0.002:
                raise ValueError(f'camera presentation timing mismatch: {name}')
        _run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(source), '-map', '0:v:0',
              '-f', 'null', '-'])
        receipts[camera] = {'source': name, 'sha256': actual_hash,
                            'codec': stream.get('codec_name'), 'frames_decoded': expected_frames,
                            'fps': expected_fps, 'width': width, 'height': height,
                            'presentation_timing_checked': True}
    return {'format': 'crest-four-camera-decode', 'origin_verified': False,
            'cameras': receipts, 'physical_visibility_reviewed': False,
            'limitations': 'Full source decode establishes readable synchronized media shape, not actual vehicle, crest, or sight-line visibility.'}
