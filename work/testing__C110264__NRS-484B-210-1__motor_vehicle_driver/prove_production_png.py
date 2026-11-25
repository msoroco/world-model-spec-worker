"""Exercise the full production PNG decoder using synthetic source shape.

All generated pixels stay in .runtime-work. This proves the CPU validation path,
not that any physical Native capture has occurred.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'tests'))
from test_pass_right_audit import attempt  # noqa: E402
from pass_right_audit import audit_delivery  # noqa: E402
from pass_right_media import PROFILE  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.scratch.resolve()
    if '.runtime-work' not in root.parts:
        raise ValueError('production-shaped synthetic pixels must stay under .runtime-work')
    root.mkdir(parents=True, exist_ok=True)
    manifest = attempt(root, 'left_signal')
    for name, dimensions in PROFILE.items():
        buffer = io.BytesIO()
        Image.new('RGB', dimensions, (12, 34, 56)).save(buffer, format='PNG')
        frame = buffer.getvalue()
        archive_path = root / (name + '.zip')
        with ZipFile(archive_path, 'w') as archive:
            for index in range(900):
                archive.writestr(f'{index:06d}.png', frame)
        manifest['cameras'][name] = {
            'path': archive_path.name,
            'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        }
    positive = audit_delivery(root, manifest)
    if not positive['production_camera_profile_verified'] or not positive['full_original_camera_decode']:
        raise AssertionError('full production profile decode did not complete')
    manifest['cameras']['rear']['sha256'] = '0' * 64
    try:
        audit_delivery(root, manifest)
    except ValueError as error:
        if 'rear camera source sha256 mismatch' not in str(error):
            raise
        negative = str(error)
    else:
        raise AssertionError('tampered original camera accepted')
    args.output.write_text(json.dumps({
        'format': 'worker-production-profile-cpu-proof',
        'source_scope': 'synthetic original-shaped source and actual decoded pixels only',
        'physical_acceptance_claimed': False,
        'frame_count': 900, 'camera_dimensions': PROFILE,
        'positive_full_decode': True, 'negative_error': negative,
        'camera_pixel_sha256': positive['camera_pixel_sha256'],
    }, indent=2) + '\n')
    print('full 3600 original-shaped PNG decode and wrong-source rejection passed')


if __name__ == '__main__':
    main()
