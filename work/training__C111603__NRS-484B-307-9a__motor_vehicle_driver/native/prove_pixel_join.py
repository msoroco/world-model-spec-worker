"""Exercise original RGB hash join with a small real FFV1 stream on CPU."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import process_original as saved


def prove():
    if not os.environ.get('TMPDIR', '').endswith('c111603-307-9a'):
        raise ValueError('Task scratch directory required')
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as name:
        folder = Path(name)
        size = 2 * 2 * 3
        frames = [bytes(((index + offset * 17) % 256 for offset in range(size)))
                  for index in range(saved.FRAMES)]
        source = folder / 'source.rgb'
        source.write_bytes(b''.join(frames))
        media = folder / 'overview.mkv'
        command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                   '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '2x2', '-r', '20',
                   '-i', str(source), '-an', '-c:v', 'ffv1', str(media)]
        subprocess.run(command, check=True, capture_output=True)
        rows = [{'source_rgb_sha256': {'overview': hashlib.sha256(frame).hexdigest()}}
                for frame in frames]
        original_cameras, original_sizes = saved.CAMERAS, saved.CAMERA_SIZES
        try:
            saved.CAMERAS = ('overview',)
            saved.CAMERA_SIZES = {'overview': (2, 2)}
            saved.verify_frame_pixels(folder, rows, False)
            changed = [dict(row) for row in rows]
            changed[319] = {'source_rgb_sha256': {'overview': '0' * 64}}
            try:
                saved.verify_frame_pixels(folder, changed, False)
            except ValueError as error:
                rejection = str(error)
            else:
                raise AssertionError('Changed original RGB frame digest was accepted')
        finally:
            saved.CAMERAS, saved.CAMERA_SIZES = original_cameras, original_sizes
        return {'format': 'c111603-real-ffv1-pixel-join-cpu-proof-v1',
                'frames_decoded': len(frames), 'size': [2, 2],
                'positive_passed': True, 'negative_rejection': rejection,
                'physical_assignment_capture': False, 'legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
