"""Independent saved-source integrity check for an exact trail attempt.

This audits original bytes and joins only. A caller still needs a full media
decode, actual-pixel review, physical-completion review and local acceptance.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess


_spec = importlib.util.spec_from_file_location('trail_saved_audit', Path(__file__).with_name('saved_audit.py'))
_saved = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_saved)
CAMERAS = ('front', 'rear', 'left', 'right')


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _confined(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('invalid saved source path')
    path = (root / relative).resolve()
    if path == root or root not in path.parents or not path.is_file():
        raise ValueError('saved source missing or outside attempt')
    return path


def audit_saved(attempt: Path, acquisition_path: Path, case_id: str) -> dict:
    """Verify a sealed acquisition inventory and return a non-acceptance report."""
    _saved._case_suffix(case_id)
    root = attempt.resolve()
    acquisition_path = acquisition_path.resolve()
    if root not in acquisition_path.parents or not acquisition_path.is_file():
        raise ValueError('acquisition outside attempt')
    acquisition = json.loads(acquisition_path.read_text(encoding='utf-8'))
    if acquisition.get('case_id') != case_id or acquisition.get('cell_id') != 'C143687':
        raise ValueError('acquisition case or cell mismatch')
    if acquisition.get('frame_count') != 900 or acquisition.get('fps') != 20:
        raise ValueError('acquisition frame contract mismatch')
    history = acquisition.get('history', {})
    original = _confined(root, history.get('path'))
    expected = history.get('sha256')
    if not expected or _sha(original) != expected:
        raise ValueError('original history hash mismatch')
    native = _saved.audit_history(original, expected, case_id)
    media = acquisition.get('camera_media')
    if not isinstance(media, dict) or set(media) != set(CAMERAS):
        raise ValueError('four camera inventory missing')
    verified = {}
    for camera in CAMERAS:
        entry = media[camera]
        path = _confined(root, entry.get('path'))
        if not entry.get('sha256') or _sha(path) != entry['sha256']:
            raise ValueError(f'{camera} camera hash mismatch')
        if path.stat().st_size == 0:
            raise ValueError(f'{camera} camera empty')
        verified[camera] = {'path': entry['path'], 'sha256': entry['sha256']}
    return {
        'case_id': case_id,
        'acquisition_sha256': _sha(acquisition_path),
        'native_source': True,
        'all_participants': bool(native['entered_corridor']),
        'time_join': native['frame_count'] == 900,
        'camera_media': verified,
        'full_video_decode': False,
        'actual_pixels': False,
        'physical_completion': False,
        'legal_judgment': None,
    }


def audit_decoded(attempt: Path, acquisition_path: Path, case_id: str,
                  *, expected_dimensions=None) -> dict:
    """Join the sealed source audit with complete original 20 Hz video decode."""
    report = audit_saved(attempt, acquisition_path, case_id)
    root = Path(attempt).resolve()
    streams = {}
    for camera, ref in report['camera_media'].items():
        if (root / ref['path']).is_symlink():
            raise ValueError('camera symlink rejected')
        path = _confined(root, ref['path'])
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=width,height,r_frame_rate:frame=best_effort_timestamp_time',
             '-show_frames', '-of', 'json', str(path)],
            capture_output=True, text=True, check=False)
        if probe.returncode:
            raise ValueError('camera probe failed')
        data = json.loads(probe.stdout)
        stream = data.get('streams', [{}])[0]
        if stream.get('r_frame_rate') != '20/1':
            raise ValueError('camera rate differs from 20 Hz')
        if expected_dimensions is not None and (
            stream.get('width'), stream.get('height')) != tuple(expected_dimensions[camera]):
            raise ValueError('camera dimensions differ')
        try:
            times = [float(row['best_effort_timestamp_time']) for row in data['frames']]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('camera frame timestamp missing') from exc
        if len(times) != 900 or any(abs((time - times[0]) - i / 20) > .001
                                     for i, time in enumerate(times)):
            raise ValueError('camera frame/time continuity failed')
        decoded = subprocess.run(
            ['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:v:0',
             '-f', 'null', '-'], capture_output=True, text=True, check=False)
        if decoded.returncode:
            raise ValueError('camera full decode failed')
        streams[camera] = {'sha256': ref['sha256'], 'decoded_frames': len(times),
                           'first_pts_s': times[0], 'last_pts_s': times[-1]}
    return {**report, 'full_video_decode': True, 'decoded_view_frames': 3600,
            'camera_streams': streams}
