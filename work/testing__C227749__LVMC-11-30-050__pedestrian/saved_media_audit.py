"""Independent full decode of a saved crossing attempt's four camera sources.

This verifies file identity and software integrity, not pedestrian visibility.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from native_capture import CAMERA_SPECS
from saved_measurement import read_attempt


def _command(args):
    completed = subprocess.run(args, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise ValueError(f"media command failed ({completed.returncode}): {completed.stderr[-500:]}")
    return completed.stdout


def _frames_from_framemd5(text):
    records = [line.split(',') for line in text.splitlines()
               if line.strip() and not line.startswith('#')]
    if not records or any(len(row) != 6 for row in records):
        raise ValueError('full decode emitted no valid frame hashes')
    frames = [int(row[1].strip()) for row in records]
    if frames != list(range(len(frames))):
        raise ValueError('decoded video frame indexes are not contiguous')
    if any(not row[5].strip() for row in records):
        raise ValueError('decoded video frame hash missing')
    return frames


def audit_media(attempt):
    root = Path(attempt).resolve()
    saved = read_attempt(root)
    joins = [json.loads(line) for line in (root/'camera-frame-joins.jsonl').read_text().splitlines() if line]
    expected = len(joins)
    if not expected:
        raise ValueError('empty camera frame joins')
    report = {'case_id': saved['case_id'], 'diagnostic_fixture': saved['diagnostic_fixture'],
              'expected_frames': expected, 'source_sha256': saved['sources_sha256'],
              'cameras': {}, 'physical_visibility': 'unconfirmed'}
    for name, (width, height) in CAMERA_SPECS.items():
        source = root/(name+'.mkv')
        probe = json.loads(_command(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                     '-show_entries', 'stream=width,height,r_frame_rate,codec_name',
                                     '-of', 'json', str(source)]))
        streams = probe.get('streams', [])
        if len(streams) != 1:
            raise ValueError(name+': exactly one video stream required')
        stream = streams[0]
        if (stream.get('width'), stream.get('height')) != (width, height):
            raise ValueError(name+': camera dimensions differ from capture profile')
        if stream.get('r_frame_rate') != '20/1':
            raise ValueError(name+': camera frame rate differs from 20 Hz')
        if not saved['diagnostic_fixture'] and stream.get('codec_name') != 'ffv1':
            raise ValueError(name+': original Native source is not lossless FFV1')
        decoded = _frames_from_framemd5(_command(['ffmpeg', '-nostdin', '-v', 'error',
                                                   '-i', str(source), '-map', '0:v:0',
                                                   '-f', 'framemd5', '-']))
        if len(decoded) != expected:
            raise ValueError(name+': decoded frame count differs from original join')
        for index, join in enumerate(joins):
            camera = join['cameras'][name]
            source_frame = camera.get('frame') if isinstance(camera, dict) else camera
            if source_frame != join['frame'] and source_frame != index:
                raise ValueError(name+': original camera frame map mismatch')
        report['cameras'][name] = {'codec': stream['codec_name'], 'width': width,
                                   'height': height, 'fps': 20,
                                   'fully_decoded_frames': len(decoded)}
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit_media(args.attempt), sort_keys=True))


if __name__ == '__main__':
    main()
