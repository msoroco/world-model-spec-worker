"""Independent saved camera/frame audit for original Native pedestrian captures."""
from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from native_capture import ASSIGNMENT, CAMERAS


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempt_root):
    root = Path(attempt_root).resolve()
    receipt = json.loads((root / 'capture-receipt.json').read_text())
    if receipt.get('format') != 'worker-original-crossing-capture' or receipt.get('assignment_id') != ASSIGNMENT:
        raise ValueError('wrong original capture receipt')
    if receipt.get('camera_capture_complete') is not True:
        raise ValueError('original four-camera capture missing')
    frame_ref = receipt['original_frames']
    frame_path = root / frame_ref['path']
    if frame_path.resolve().parent != root or _sha(frame_path) != frame_ref['sha256']:
        raise ValueError('original frame source hash mismatch')
    rows = json.loads(frame_path.read_text())
    if len(rows) != receipt['frame_count'] or not rows:
        raise ValueError('original frame count mismatch')
    if [row['frame'] for row in rows] != list(range(receipt['first_frame'], receipt['last_frame'] + 1)):
        raise ValueError('original frame sequence mismatch')
    sources = receipt.get('camera_sources')
    if not isinstance(sources, dict) or set(sources) != set(CAMERAS):
        raise ValueError('four original camera sources missing')
    for name in CAMERAS:
        ref = sources[name]
        path = root / ref['path']
        if path.resolve().parent != root or _sha(path) != ref['sha256']:
            raise ValueError(f'{name} original camera source hash mismatch')
        if ref['frame_count'] != len(rows):
            raise ValueError(f'{name} original camera frame count mismatch')
        expected_members = [f"{row['frame']:08d}.png" for row in rows]
        with ZipFile(path) as archive:
            if archive.namelist() != expected_members:
                raise ValueError(f'{name} original camera frame map mismatch')
            for row, member in zip(rows, expected_members):
                binding = row.get('camera_frames', {}).get(name)
                payload = archive.read(member)
                if binding != {'member': member, 'sha256': hashlib.sha256(payload).hexdigest()}:
                    raise ValueError(f'{name} original camera pixel binding mismatch')
                with Image.open(BytesIO(payload)) as image:
                    image.verify()
                with Image.open(BytesIO(payload)) as image:
                    if image.format != 'PNG' or list(image.size) != ref['dimensions']:
                        raise ValueError(f'{name} original camera image mismatch')
                    image.load()
    return {'format': 'worker-original-camera-audit', 'assignment_id': ASSIGNMENT,
            'case_id': receipt['case_id'], 'frame_count': len(rows),
            'decoded_images': len(rows) * len(CAMERAS),
            'capture_receipt_sha256': _sha(root / 'capture-receipt.json'),
            'physical_acceptance': False, 'legal_verdict': None}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt-root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.attempt_root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
