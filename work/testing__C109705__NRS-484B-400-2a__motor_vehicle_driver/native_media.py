"""Encode four retained Native PNG archives as named lossless camera sources."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

from saved_delivery import CAMERAS


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(attempt: Path, output: Path, dimensions: dict[str, tuple[int, int]]) -> dict:
    """Decode each original PNG and publish four MKVs only after all encoders exit.

    ``attempt`` is an immutable original Native source directory. ``output`` is
    an existing runtime materialization. No source is rewritten.
    """
    attempt, output = Path(attempt), Path(output)
    if not output.is_dir() or attempt.resolve() == output.resolve():
        raise ValueError('existing separate runtime output required')
    if set(dimensions) != set(CAMERAS):
        raise ValueError('exact four camera dimensions required')
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    mapping_path = attempt / 'video_frames.jsonl'
    mapping_ref = acquisition.get('video_frames.jsonl', {})
    if (mapping_path.is_symlink() or not mapping_path.is_file() or
            mapping_ref.get('kind') != 'original_native' or
            _sha(mapping_path) != mapping_ref.get('sha256')):
        raise ValueError('original Native frame map source differs')
    rows = [json.loads(line) for line in mapping_path.read_text().splitlines()
            if line.strip()]
    if not rows or any(row.get('video_frame') != index for index, row in enumerate(rows)):
        raise ValueError('original Native frame map is incomplete')
    if any((output / (name + '.mkv')).exists() for name in CAMERAS):
        raise ValueError('refusing to overwrite named camera sources')
    stage = Path(tempfile.mkdtemp(prefix='native-media-', dir=output.parent))
    try:
        hashes = {}
        for name in sorted(CAMERAS):
            source = attempt / (name + '.zip')
            declared = acquisition.get('media', {}).get(name, {})
            width, height = dimensions[name]
            if (source.is_symlink() or not source.is_file() or
                    declared.get('kind') != 'original_native' or
                    declared.get('path') != source.name or
                    _sha(source) != declared.get('sha256') or
                    type(width) is not int or type(height) is not int or
                    width <= 0 or height <= 0):
                raise ValueError('original Native camera source differs: ' + name)
            target = stage / (name + '.mkv')
            command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                       '-f', 'image2pipe', '-framerate', '20', '-vcodec', 'png',
                       '-i', 'pipe:0', '-frames:v', str(len(rows)), '-an',
                       '-c:v', 'ffv1', '-pix_fmt', 'yuv444p', str(target)]
            process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.PIPE)
            try:
                with zipfile.ZipFile(source) as archive:
                    expected = [f'{index:04d}-{row["frame"]}.png'
                                for index, row in enumerate(rows)]
                    if sorted(archive.namelist()) != sorted(expected):
                        raise ValueError('original camera frame coverage differs: ' + name)
                    for filename in expected:
                        raw = archive.read(filename)
                        with Image.open(io.BytesIO(raw)) as image:
                            image.load()
                            if image.size != (width, height):
                                raise ValueError('original camera dimensions differ: ' + name)
                        process.stdin.write(raw)
                process.stdin.close()
                error = process.stderr.read()
                if process.wait() != 0 or not target.is_file() or not target.stat().st_size:
                    raise ValueError('original camera encoder failed: ' + name + ' ' +
                                     error.decode(errors='replace')[-300:])
            except BaseException:
                if process.poll() is None:
                    process.kill()
                process.wait()
                raise
            finally:
                process.stderr.close()
            hashes[name] = _sha(target)
        for name in sorted(CAMERAS):
            os.replace(stage / (name + '.mkv'), output / (name + '.mkv'))
        return {'frames': len(rows), 'source_frame_map_sha256': _sha(mapping_path),
                'original_camera_sha256': {name: acquisition['media'][name]['sha256']
                                           for name in sorted(CAMERAS)},
                'encoded_camera_sha256': hashes,
                'physical_visibility_verified': False}
    finally:
        shutil.rmtree(stage, ignore_errors=True)
