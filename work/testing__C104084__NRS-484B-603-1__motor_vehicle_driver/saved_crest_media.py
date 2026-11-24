"""Decode all original hill-crest camera streams after source binding.

This verifies saved pixels and timing, not camera visibility or physical success.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from saved_crest_audit import CAMERAS, FRAME_COUNT, _source, audit


def _run(args: list[str]) -> bytes:
    process = subprocess.run(args, capture_output=True, check=False)
    if process.returncode:
        raise ValueError(f'camera decode tool failed: {process.stderr.decode(errors="replace")[-500:]}')
    return process.stdout


def decode_camera(path: Path, *, width: int, height: int) -> dict:
    """Require exactly 900 complete frames at 20 Hz and hash decoded pixels."""
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise ValueError('positive camera dimensions required')
    probe = json.loads(_run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                             '-show_entries', 'stream=width,height,avg_frame_rate',
                             '-of', 'json', str(path)]))
    streams = probe.get('streams', [])
    if len(streams) != 1:
        raise ValueError('one original video stream required')
    stream = streams[0]
    if (stream.get('width'), stream.get('height'), stream.get('avg_frame_rate')) != (width, height, '20/1'):
        raise ValueError('original camera dimensions or 20 Hz rate differs')
    command = ['ffmpeg', '-v', 'error', '-i', str(path), '-map', '0:v:0',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-vsync', '0', '-']
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest = hashlib.sha256()
    decoded_bytes = 0
    try:
        assert process.stdout is not None
        for block in iter(lambda: process.stdout.read(1024 * 1024), b''):
            digest.update(block)
            decoded_bytes += len(block)
        stderr = process.stderr.read() if process.stderr is not None else b''
        if process.wait():
            raise ValueError(f'camera decode tool failed: {stderr.decode(errors="replace")[-500:]}')
    finally:
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
        if process.poll() is None:
            process.kill()
            process.wait()
    frame_bytes = width * height * 3
    if decoded_bytes != frame_bytes * FRAME_COUNT:
        raise ValueError('complete original 900-frame camera decode required')
    return {'width': width, 'height': height, 'fps': 20, 'frame_count': FRAME_COUNT,
            'decoded_rgb24_sha256': digest.hexdigest()}


def audit_media(attempt, manifest: dict) -> dict:
    """Join exact saved motion/frame sources to four fully decoded cameras."""
    source_proof = audit(attempt, manifest)
    dimensions = manifest.get('camera_dimensions')
    if not isinstance(dimensions, dict) or set(dimensions) != set(CAMERAS):
        raise ValueError('four original camera dimensions required')
    cameras = {}
    for camera in CAMERAS:
        size = dimensions[camera]
        if not isinstance(size, list) or len(size) != 2:
            raise ValueError('camera width and height required')
        path, digest = _source(Path(attempt), manifest['camera_sources'][camera])
        cameras[camera] = {'source_sha256': digest,
                           **decode_camera(path, width=size[0], height=size[1])}
    source_proof['format'] = 'worker-crest-saved-media-audit'
    source_proof['camera_decodes'] = cameras
    source_proof['checks']['full_video_decode'] = True
    source_proof['checks']['actual_pixels'] = True
    return source_proof


def main():
    parser = argparse.ArgumentParser(description='Audit original hill-crest camera pixels')
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    proof = audit_media(args.attempt, manifest)
    output = Path(args.output)
    if output.exists():
        raise ValueError('retain prior media audit; choose a fresh output')
    output.write_text(json.dumps(proof, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
