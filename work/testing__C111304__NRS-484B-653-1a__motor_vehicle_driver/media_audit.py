"""Independent saved-camera integrity and decode audit for C111304.

The camera plan and media inventory are local operator inputs. A CPU fixture can
prove the decoder path, but cannot prove that a person or property is visible.
"""
from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
import subprocess

CAMERAS = ('front', 'rear', 'left', 'right')
CASE_PREFIX = 'testing__C111304__NRS-484B-653-1a__motor_vehicle_driver__'


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _run(command: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise ValueError(f'media tool failed: {command[0]}: {result.stderr[-400:]}')
    return result


def audit_media(attempt: Path, receipt: dict, inventory: dict, camera_plan: dict,
                *, allow_diagnostic: bool = False) -> dict:
    """Verify four attempt-confined encoded streams, then fully decode each.

    The inventory binds exact encoded-file hashes to the sealed Native receipt.
    Frame readback hashes in original-cameras.jsonl remain separate evidence;
    encoded pixels are not assumed byte-identical to original sensor packets.
    """
    from encounter import CASES

    allowed = {CASE_PREFIX + case.case_id for case in CASES}
    case_id = receipt.get('case_id')
    if case_id not in allowed or inventory.get('case_id') != case_id:
        raise ValueError('exact case identity mismatch')
    if inventory.get('source_kind') != 'original_encoded' and not (
        allow_diagnostic and inventory.get('source_kind') == 'synthetic_fixture'
    ):
        raise ValueError('original encoded camera source required')
    if receipt.get('frame_count') != 900 or receipt.get('original_fps') != 20:
        raise ValueError('original acquisition duration or cadence mismatch')
    sealed_path = attempt / 'native-receipt.json'
    if not sealed_path.is_file() or sealed_path.is_symlink():
        raise ValueError('native receipt missing or redirected')
    if inventory.get('native_receipt_sha256') != _digest(sealed_path):
        raise ValueError('native receipt source hash mismatch')
    try:
        sealed = json.loads(sealed_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('native receipt decode failed') from exc
    if sealed != receipt:
        raise ValueError('native receipt content mismatch')
    plan_source = json.dumps(camera_plan, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if hashlib.sha256(plan_source).hexdigest() != receipt.get('camera_plan_sha256'):
        raise ValueError('camera plan source hash mismatch')
    if set(inventory.get('cameras', {})) != set(CAMERAS) or set(camera_plan.get('cameras', {})) != set(CAMERAS):
        raise ValueError('four camera entries required')
    decoded = {}
    used = set()
    for camera in CAMERAS:
        item = inventory['cameras'][camera]
        name = item.get('path')
        if not isinstance(name, str) or not name or Path(name).is_absolute():
            raise ValueError('camera media path invalid')
        candidate = attempt / name
        path = candidate.resolve()
        if (attempt.resolve() not in path.parents or not path.is_file() or
                candidate.is_symlink() or path in used):
            raise ValueError('camera media missing, redirected or reused')
        used.add(path)
        if _digest(path) != item.get('sha256'):
            raise ValueError(f'{camera} encoded media hash mismatch')
        probed = _run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                       '-count_frames', '-show_entries',
                       'stream=width,height,avg_frame_rate,nb_read_frames',
                       '-of', 'json', str(path)])
        streams = json.loads(probed.stdout).get('streams', [])
        if len(streams) != 1:
            raise ValueError(f'{camera} video stream missing')
        stream = streams[0]
        expected = camera_plan['cameras'][camera]
        if (stream.get('width'), stream.get('height')) != (expected.get('width'), expected.get('height')):
            raise ValueError(f'{camera} dimensions differ from camera plan')
        try:
            fps = Fraction(stream['avg_frame_rate'])
            frames = int(stream['nb_read_frames'])
        except (KeyError, ValueError, ZeroDivisionError) as exc:
            raise ValueError(f'{camera} frame metadata missing') from exc
        if fps != 20 or frames != 900:
            raise ValueError(f'{camera} frame count or cadence mismatch')
        _run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-map', '0:v:0',
              '-f', 'null', '-'])
        decoded[camera] = {'encoded_sha256': item['sha256'], 'frames': frames,
                           'fps': 20, 'width': stream['width'], 'height': stream['height'],
                           'full_decode': True}
    return {'case_id': case_id, 'native_receipt_sha256': inventory['native_receipt_sha256'],
            'camera_plan_sha256': receipt['camera_plan_sha256'], 'cameras': decoded,
            'source_kind': inventory['source_kind'],
            'actual_body_visibility': False, 'physical_completion': False,
            'legal_judgment': None}
