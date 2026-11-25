"""Exercise the current saved meter's original FFV1 RGB join with real bytes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import current_contrast_saved as saved


def prove():
    if not os.environ.get('TMPDIR', '').endswith('c146314-210-1'):
        raise ValueError('Task-specific scratch directory required')
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as name:
        folder = Path(name)
        frames = [bytes((i + j * 13) % 256 for j in range(12))
                  for i in range(saved.FRAMES)]
        (folder / 'source.rgb').write_bytes(b''.join(frames))
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '2x2', '-r', '20',
                        '-i', str(folder / 'source.rgb'), '-an', '-c:v', 'ffv1',
                        str(folder / 'overview.mkv')], check=True, capture_output=True)
        rows = [{'source_rgb_sha256': {'overview': hashlib.sha256(frame).hexdigest()}}
                for frame in frames]
        original = saved.CAMERAS
        try:
            saved.CAMERAS = {'overview': (2, 2)}
            saved.verify_video(folder, rows, False)
            rows[415]['source_rgb_sha256']['overview'] = '0' * 64
            try:
                saved.verify_video(folder, rows, False)
            except ValueError as exc:
                rejection = str(exc)
            else:
                raise AssertionError('Changed decoded RGB frame accepted')
        finally:
            saved.CAMERAS = original
    return {'format': 'c146314-current-contrast-real-ffv1-cpu-proof-v1',
            'frames_decoded': 600, 'small_test_resolution': [2, 2],
            'positive_passed': True, 'negative_rejection': rejection,
            'assignment_native_observed': False, 'legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
