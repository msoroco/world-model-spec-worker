"""Saved-only conversion of sealed original C111304 camera PNG frames."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from native_acquisition import CAMERAS


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError('original camera source missing or redirected')


def encode_original_cameras(attempt: Path, camera_plan: dict, *, ffmpeg='ffmpeg') -> dict:
    """Require every sealed PNG, then make four FFV1 streams and an inventory."""
    from media_audit import audit_media

    receipt_path = attempt / 'native-receipt.json'
    camera_rows_path = attempt / 'original-cameras.jsonl'
    _safe(receipt_path)
    _safe(camera_rows_path)
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    if receipt.get('frame_count') != 900 or receipt.get('original_fps') != 20:
        raise ValueError('sealed original timebase mismatch')
    if _sha(camera_rows_path) != receipt.get('original_cameras_sha256'):
        raise ValueError('sealed original camera trace hash mismatch')
    rows = [json.loads(line) for line in camera_rows_path.read_text(encoding='utf-8').splitlines()]
    start = receipt.get('first_original_frame')
    if type(start) is not int or len(rows) != 900:
        raise ValueError('900 original camera rows required')
    if set(camera_plan.get('cameras', {})) != set(CAMERAS):
        raise ValueError('four camera plan entries required')
    for index, row in enumerate(rows):
        frame = start + index
        if row.get('original_frame') != frame or set(row.get('camera_sha256', {})) != set(CAMERAS):
            raise ValueError('original camera frame or channel join mismatch')
        for name in CAMERAS:
            path = attempt / 'cameras' / name / f'{frame:06d}.png'
            _safe(path)
            if _sha(path) != row['camera_sha256'][name]:
                raise ValueError(name + ' original PNG hash mismatch')
    encoded_root = attempt / 'encoded'
    if encoded_root.exists():
        raise ValueError('encoded attempt output already exists')
    encoded_root.mkdir()
    cameras = {}
    for name in CAMERAS:
        source = attempt / 'cameras' / name / '%06d.png'
        output = encoded_root / (name + '.mkv')
        command = [ffmpeg, '-v', 'error', '-xerror', '-framerate', '20',
                   '-start_number', str(start), '-i', str(source),
                   '-frames:v', '900', '-c:v', 'ffv1', str(output)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        if result.returncode or not output.is_file():
            raise ValueError(name + ' saved FFV1 conversion failed: ' + result.stderr[-300:])
        cameras[name] = {'path': str(output.relative_to(attempt)), 'sha256': _sha(output)}
    inventory = {'case_id': receipt['case_id'], 'source_kind': 'original_encoded',
                 'native_receipt_sha256': _sha(receipt_path), 'cameras': cameras}
    audit_media(attempt, receipt, inventory, camera_plan)
    (attempt / 'camera-media-inventory.json').write_text(
        json.dumps(inventory, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return inventory
