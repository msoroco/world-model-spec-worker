"""Decode every saved camera stream; no physical pixel interpretation."""

import argparse
import json
from pathlib import Path
import subprocess

from measure_original import CAMERAS, measure, sha


def audit_media(attempt, cameras, frame_count):
    attempt = Path(attempt)
    sealed = json.loads((attempt / 'captured-source-hashes.json').read_text())
    if sealed.get('source_kind') != 'original_native_capture':
        raise ValueError('Original Native media seal missing')
    if set(cameras) != set(CAMERAS):
        raise ValueError('Four exact camera names required')
    observations = {}
    for name in CAMERAS:
        path = attempt / (name + '.mkv')
        if not path.is_file() or sealed.get('sha256', {}).get(path.name) != sha(path):
            raise ValueError('Sealed camera source missing or changed: ' + name)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
            '-select_streams', 'v:0', '-show_entries',
            'stream=width,height,avg_frame_rate,nb_read_frames,codec_name',
            '-of', 'json', str(path)], capture_output=True, text=True)
        if probe.returncode:
            raise ValueError('Camera media probe failed: ' + name)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1:
            raise ValueError('Camera video stream missing: ' + name)
        stream = streams[0]
        spec = cameras[name]
        if (stream.get('codec_name') != 'ffv1' or
                stream.get('width') != spec['width'] or
                stream.get('height') != spec['height'] or
                stream.get('avg_frame_rate') != '20/1' or
                int(stream.get('nb_read_frames', -1)) != frame_count):
            raise ValueError('Camera media profile or duration differs: ' + name)
        decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror',
            '-i', str(path), '-map', '0:v:0', '-f', 'null', '-'],
            capture_output=True, text=True)
        if decoded.returncode:
            raise ValueError('Full camera decode failed: ' + name)
        observations[name] = {'width': stream['width'],
            'height': stream['height'], 'frames': frame_count,
            'codec': 'ffv1', 'sha256': sha(path), 'full_decode': True}
    return {'format': 'c183370-four-camera-media-audit',
            'source_kind': 'original_native_capture',
            'frame_count': frame_count, 'cameras': observations,
            'actual_pixels_interpreted': False,
            'physical_completion': None, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    if config.get('case_id') not in {
            config.get('assignment_id', '') + '__probe_a',
            config.get('assignment_id', '') + '__probe_b',
            config.get('assignment_id', '') + '__probe_c',
            config.get('assignment_id', '') + '__probe_d'}:
        raise ValueError('Exact media case identity differs')
    measurement = measure(args.attempt, config['case_id'])
    result = audit_media(args.attempt, config['cameras'], config['frame_count'])
    result['case_id'] = config['case_id']
    result['source_seal_sha256'] = measurement['source_seal_sha256']
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
