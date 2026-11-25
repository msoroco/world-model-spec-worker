"""Compose and independently decode four original camera archives."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

_SPEC = importlib.util.spec_from_file_location('native_capture', Path(__file__).with_name('native_capture.py'))
_CAPTURE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CAPTURE)
CAMERAS = _CAPTURE.CAMERAS
FRAMES = _CAPTURE.FRAMES
audit_original_pixels = _CAPTURE.audit_original_pixels
PRODUCTION_PROFILE = {"overview": (1920, 1080),
                      "approach": (1280, 720),
                      "reference_corner": (1280, 720),
                      "driver_reference": (1280, 720)}


def _sealed(root, ref):
    if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}:
        raise ValueError('source path/hash required')
    original = root / ref['path']
    path = original.resolve()
    if original.is_symlink() or path.parent != root or not path.is_file():
        raise ValueError('source escapes original attempt')
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
        raise ValueError('original source hash drift')
    return path


def _decode(path, count, width, height):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                            '-count_frames', '-show_entries',
                            'stream=width,height,r_frame_rate,nb_read_frames',
                            '-of', 'json', str(path)], capture_output=True, text=True)
    if probe.returncode:
        raise ValueError('ffprobe rejected composed video')
    streams = json.loads(probe.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('one original video stream required')
    stream = streams[0]
    if (stream.get('width'), stream.get('height'), stream.get('r_frame_rate'),
            int(stream.get('nb_read_frames', -1))) != (width, height, '20/1', count):
        raise ValueError('composed video frame rate, count or dimensions differ')
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                              '-map', '0:v:0', '-f', 'null', '-'],
                             capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError('composed video full decode failed')


def compose(root, *, profile, diagnostic_fixture=False):
    """Use sealed original PNGs as the sole encoder input; never synthesize frames."""
    root = Path(root).resolve()
    if set(profile) != set(CAMERAS):
        raise ValueError('four original camera dimensions required')
    if not diagnostic_fixture and any(tuple(profile[name]) != PRODUCTION_PROFILE[name]
                                      for name in CAMERAS):
        raise ValueError('production camera dimensions required')
    audit_original_pixels(root, expected_dimensions=None if diagnostic_fixture else PRODUCTION_PROFILE)
    if (root / 'video-media.json').exists():
        raise ValueError('composed media already exists')
    packet = json.loads((root / 'encounter-packet.json').read_text(encoding='utf-8'))
    media = json.loads(_sealed(root, packet['media']).read_text(encoding='utf-8'))
    frames = json.loads(_sealed(root, packet['camera_frames']).read_text(encoding='utf-8'))
    refs = {}
    created = []
    try:
        for camera in CAMERAS:
            width, height = profile[camera]
            output = root / (camera + '.mkv')
            if output.exists():
                raise ValueError('composed video already exists')
            created.append(output)
            with ZipFile(_sealed(root, media[camera])) as archive:
                process = subprocess.Popen(
                    ['ffmpeg', '-v', 'error', '-xerror', '-f', 'image2pipe',
                     '-framerate', '20', '-vcodec', 'png', '-i', 'pipe:0',
                     '-frames:v', str(FRAMES), '-an', '-c:v', 'ffv1',
                     '-level', '3', str(output)], stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                try:
                    for frame in frames[camera]:
                        process.stdin.write(archive.read(f'{frame:08d}.png'))
                    process.stdin.close()
                    error = process.stderr.read()
                    code = process.wait()
                except Exception:
                    process.kill()
                    process.wait()
                    raise
                finally:
                    process.stderr.close()
                if code:
                    raise ValueError('lossless composed video encode failed: ' + error.decode(errors='replace')[-200:])
            _decode(output, FRAMES, width, height)
            refs[camera] = {'path': output.name,
                            'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                            'width': width, 'height': height, 'frames': FRAMES}
        manifest = {'case_id': packet['case_id'], 'fps': 20,
                    'original_frames': FRAMES, 'camera_videos': refs,
                    'diagnostic_fixture': diagnostic_fixture,
                    'physical_review': 'pending', 'legal_judgment': 'unresolved'}
        path = root / 'video-media.json'
        path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        return {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def audit_composed(root, manifest_ref):
    root = Path(root).resolve()
    manifest = json.loads(_sealed(root, manifest_ref).read_text(encoding='utf-8'))
    packet = json.loads((root / 'encounter-packet.json').read_text(encoding='utf-8'))
    if manifest.get('case_id') != packet.get('case_id') or manifest.get('original_frames') != FRAMES:
        raise ValueError('composed video case or duration differs')
    refs = manifest.get('camera_videos')
    if not isinstance(refs, dict) or set(refs) != set(CAMERAS) or manifest.get('fps') != 20:
        raise ValueError('four composed 20 Hz videos required')
    if manifest.get('diagnostic_fixture') is not True and any(
            (refs[camera].get('width'), refs[camera].get('height')) != PRODUCTION_PROFILE[camera]
            for camera in CAMERAS):
        raise ValueError('production camera profile differs')
    for camera in CAMERAS:
        item = refs[camera]
        path = _sealed(root, {'path': item['path'], 'sha256': item['sha256']})
        _decode(path, FRAMES, item['width'], item['height'])
    return {'case_id': packet['case_id'], 'full_video_decode': True,
            'original_frames': FRAMES, 'physical_review': 'pending'}
