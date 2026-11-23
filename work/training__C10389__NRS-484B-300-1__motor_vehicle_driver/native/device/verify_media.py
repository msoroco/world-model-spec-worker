"""Verify every retained source camera and the composed review video."""
import hashlib
import json
from pathlib import Path
import subprocess

VIEWS = {
    'overview.mkv': (1920, 1080),
    'approach.mkv': (1280, 720),
    'reference_corner.mkv': (1280, 720),
    'driver_reference.mkv': (1280, 720),
    'raw.mkv': (3840, 1800),
}


def verify(folder, frames):
    folder = Path(folder)
    if type(frames) is not int or frames < 1:
        raise ValueError('positive expected frame count required')
    hashes = {}
    for name, dimensions in VIEWS.items():
        path = folder / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
            '-select_streams', 'v:0', '-show_entries',
            'stream=codec_name,nb_read_frames,width,height,r_frame_rate',
            '-of', 'json', str(path)], capture_output=True, text=True,
            timeout=120, check=True)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1:
            raise ValueError('one video stream required: ' + name)
        stream = streams[0]
        if (stream.get('codec_name') != 'ffv1' or
                stream.get('nb_read_frames') != str(frames) or
                stream.get('r_frame_rate') != '20/1' or
                (stream.get('width'), stream.get('height')) != dimensions):
            raise ValueError('camera profile or frame count: ' + name)
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror',
            '-i', str(path), '-f', 'null', '-'], capture_output=True,
            text=True, timeout=180, check=True)
        hashes[name] = digest
    return hashes
