"""Independent saved-source integrity check for an exact trail attempt.

This audits original bytes and joins only. A caller still needs a full media
decode, actual-pixel review, physical-completion review and local acceptance.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


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
