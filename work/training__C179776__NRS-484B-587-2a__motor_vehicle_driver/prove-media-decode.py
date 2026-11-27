"""Decode the exact synthetic four-view profile; no original capture claim."""

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / '.runtime-work' / 'c179776-media-decode'
SCRATCH.mkdir(parents=True, exist_ok=True)
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def command(argv):
    result = subprocess.run(argv, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr[-1200:])
    return result.stdout


with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
    folder = Path(directory)
    decoded = {}
    for name, width, height in CAMERAS:
        path = folder / (name + '.mkv')
        command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                 '-i', f'color=c=gray:s={width}x{height}:r=20:d=30',
                 '-frames:v', '600', '-c:v', 'libx264', '-preset', 'ultrafast',
                 '-crf', '45', '-pix_fmt', 'yuv420p', '-y', str(path)])
        probe = json.loads(command(['ffprobe', '-v', 'error', '-select_streams',
                                    'v:0', '-count_frames', '-show_entries',
                                    'stream=width,height,r_frame_rate,nb_read_frames',
                                    '-of', 'json', str(path)]))['streams'][0]
        if (probe['width'], probe['height'], probe['r_frame_rate'],
                int(probe['nb_read_frames'])) != (width, height, '20/1', 600):
            raise AssertionError((name, probe))
        command(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(path),
                 '-map', '0:v:0', '-f', 'null', '-'])
        decoded[name] = {'width': width, 'height': height, 'frames': 600}
    print(json.dumps({'passed': True, 'source_kind': 'synthetic_media',
                      'full_video_decode_claimed': True,
                      'original_native_video_decode_claimed': False,
                      'views': decoded}, sort_keys=True))
