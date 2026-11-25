"""Encode audited original camera PNG sequences as lossless source videos."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from native_history_capture import CAMERAS, audit_media


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _probe(path):
    result = subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_entries',
        'stream=width,height,avg_frame_rate,nb_read_frames,codec_name',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(result.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('one decoded camera stream required')
    return streams[0]


def encode(attempt, output, *, camera_dimensions):
    attempt, output = Path(attempt), Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('fresh empty lossless video directory required')
    audit = audit_media(attempt, camera_dimensions=camera_dimensions)
    count = audit['joined_original_frames']
    output.mkdir(parents=True, exist_ok=True)
    videos = {}
    for name in CAMERAS:
        target = output / (name + '.mkv')
        source = attempt / 'original-frames' / (name + '-%06d.png')
        subprocess.run([
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
            '-framerate', '20', '-start_number', '0', '-i', str(source),
            '-frames:v', str(count), '-an', '-c:v', 'ffv1', '-level', '3',
            str(target)], capture_output=True, text=True, check=True)
        stream = _probe(target)
        if (stream.get('codec_name') != 'ffv1' or
                [stream.get('width'), stream.get('height')] != list(camera_dimensions[name]) or
                stream.get('avg_frame_rate') != '20/1' or
                int(stream.get('nb_read_frames', -1)) != count):
            raise ValueError('lossless camera decode/profile differs: ' + name)
        videos[name] = {'path': target.name,
                        'sha256': _sha(target),
                        'decoded_frames': count, 'dimensions': list(camera_dimensions[name])}
    return {'source_frame_count': count, 'fps': 20, 'encoding': 'ffv1',
            'videos': videos, 'physical_acceptance': False}


def main():
    parser = argparse.ArgumentParser(description='Encode audited C125763 camera PNGs')
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    site = json.loads((Path(args.attempt) / 'site-context.json').read_text())
    print(json.dumps(encode(args.attempt, args.output,
                            camera_dimensions=site['camera_dimensions']), sort_keys=True))


if __name__ == '__main__':
    main()
