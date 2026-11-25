"""Recorded-only source join and full camera decode for C111331 red entry.

This validates original acquisition identity. It does not interpret signal
pixels, official status, pedestrian permission, or legal compliance.
"""

import hashlib
import json
from pathlib import Path
import subprocess

from native_red import CAMERAS, FRAMES, check_plan, measure_entry


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def join_original(samples, frame_map, camera_rows, config):
    check_plan(config)
    if len(samples) != FRAMES or len(frame_map) != FRAMES or len(camera_rows) != FRAMES * len(CAMERAS):
        raise ValueError('Incomplete original 600-frame four-camera source')
    expected_names = {name for name, _, _, _ in CAMERAS}
    camera_by_frame = {}
    for row in camera_rows:
        index, name = row.get('video_frame'), row.get('camera')
        if type(index) is not int or index < 0 or index >= FRAMES or name not in expected_names:
            raise ValueError('Unknown original camera/frame')
        key = (index, name)
        if key in camera_by_frame:
            raise ValueError('Duplicate original camera/frame')
        camera_by_frame[key] = row
    for index, (sample, mapped) in enumerate(zip(samples, frame_map)):
        frame = sample.get('native_frame')
        if (type(frame) is not int or sample.get('video_frame') != index or
                mapped.get('video_frame') != index or mapped.get('native_frame') != frame or
                mapped.get('carla_frame') != frame or sample.get('time_s') != mapped.get('time_s')):
            raise ValueError('Original walker/FrameMap identity differs')
        if index and (frame <= samples[index - 1]['native_frame'] or
                      sample['time_s'] <= samples[index - 1]['time_s']):
            raise ValueError('Original frames/times do not increase')
        pixels = sample.get('source_rgb_sha256')
        if not isinstance(pixels, dict) or set(pixels) != expected_names or mapped.get('source_rgb_sha256') != pixels:
            raise ValueError('Original RGB hash map differs')
        for name, width, height, _ in CAMERAS:
            camera = camera_by_frame[(index, name)]
            digest = pixels[name]
            if (camera.get('native_frame') != frame or camera.get('time_s') != sample['time_s'] or
                    camera.get('width') != width or camera.get('height') != height or
                    camera.get('source_path') != name + '.mkv' or
                    camera.get('source_rgb_sha256') != digest or
                    not isinstance(digest, str) or len(digest) != 64):
                raise ValueError('Original camera pixel/frame source differs')
    measured = measure_entry(samples, config)
    return {'frames': FRAMES, 'camera_rows': len(camera_rows),
            'first_roadway_footprint_frame': measured['first_roadway_footprint_frame'],
            'original_source_join_passed': True,
            'governing_head_review_required': True,
            'other_device_review_required': True,
            'legal_verdict_claimed': False}


def full_decode(path, width, height):
    probe = subprocess.run([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,nb_read_frames', '-of', 'json', str(path)],
        capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get('streams', [])
    if len(streams) != 1 or (streams[0].get('width'), streams[0].get('height')) != (width, height) or \
            streams[0].get('nb_read_frames') != str(FRAMES):
        raise ValueError('Original camera dimensions/frame count differ: ' + path.name)
    decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror',
                              '-i', str(path), '-map', '0:v:0', '-f', 'null', '-'],
                             capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError('Full original camera decode failed: ' + path.name)
    return {'path': path.name, 'sha256': sha(path), 'frames': FRAMES,
            'width': width, 'height': height, 'full_decode': True}


def audit_attempt(attempt, config):
    root = Path(attempt)
    report = json.loads((root / 'native-capture-report.json').read_text())
    seal = json.loads((root / 'capture-seal.json').read_text())
    if (report.get('error') is not None or report.get('frames') != FRAMES or
            report.get('restoration', {}).get('restored') is not True or
            seal.get('format') != 'worker-sealed-capture' or seal.get('frames') != FRAMES or
            seal.get('provenance_kind') != 'native'):
        raise ValueError('Unsealed or unrestored original Native capture')
    required = ['red-entry-original.jsonl', 'video_frames.jsonl', 'camera-sources.jsonl',
                'trace.jsonl', *[name + '.mkv' for name, _, _, _ in CAMERAS]]
    recorded = seal.get('sources', {})
    for name in required:
        source = root / name
        if not source.is_file():
            raise ValueError('Missing original Native source: ' + name)
        if name not in recorded or recorded[name] != sha(source):
            raise ValueError('Original Native source seal differs: ' + name)
    joined = join_original(rows(root / 'red-entry-original.jsonl'),
                           rows(root / 'video_frames.jsonl'),
                           rows(root / 'camera-sources.jsonl'), config)
    videos = [full_decode(root / (name + '.mkv'), width, height)
              for name, width, height, _ in CAMERAS]
    return {'format': 'c111331-red-entry-original-source-audit-v1',
            'case_id': config['case_id'], 'join': joined, 'videos': videos,
            'capture_seal_sha256': sha(root / 'capture-seal.json'),
            'physical_pixels_interpreted': False,
            'device_governance_verified': False,
            'legal_verdict_claimed': False}
