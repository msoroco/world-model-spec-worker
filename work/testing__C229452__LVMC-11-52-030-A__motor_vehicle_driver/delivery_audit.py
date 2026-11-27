"""Independent diagnostic audit of original sources, frame joins and all video pixels."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from physical_completion import evaluate

VIEWS = {'overview': (1920, 1080), 'approach': (1280, 720),
         'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(attempt, case):
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    if config['case']['case_id'] != case:
        raise ValueError('exact case identity mismatch')
    for name in ('original-red-curb-events.jsonl', 'red-curb-context.json',
                 'camera-frame-map.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                 'diagnostic-source-note.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    note = json.loads((attempt / 'diagnostic-source-note.json').read_text())
    events = rows(attempt / 'original-red-curb-events.jsonl')
    traces = rows(attempt / 'trace.jsonl')
    mappings = rows(attempt / 'camera-frame-map.jsonl')
    frames = rows(attempt / 'video_frames.jsonl')
    if not note or len(events) < 2 or not traces or len(traces) != len(mappings) or len(traces) != len(frames):
        raise ValueError('source or original frame history incomplete')
    for index, (trace, mapping, frame) in enumerate(zip(traces, mappings, frames)):
        if trace['frame'] != mapping['native_frame'] or mapping['frame_index'] != index:
            raise ValueError('source/video frame time join mismatch')
        if abs(trace['time_s'] - mapping['time_s']) > .001:
            raise ValueError('trace and camera map time join mismatch')
        if set(mapping['camera_frames']) != set(VIEWS) or any(
                value != trace['frame'] for value in mapping['camera_frames'].values()):
            raise ValueError('four-camera original frame join mismatch')
        if frame['native_frame'] != trace['frame']:
            raise ValueError('video frame identity mismatch')
    hashes = {}
    for view, dimensions in VIEWS.items():
        path = attempt / (view + '.mkv')
        if not path.is_file():
            raise ValueError('Missing original camera: ' + view)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                '-count_frames', '-show_entries', 'stream=width,height,nb_read_frames',
                                '-of', 'json', str(path)], capture_output=True, text=True, check=True)
        stream = json.loads(probe.stdout)['streams'][0]
        if (stream['width'], stream['height'], int(stream['nb_read_frames'])) != (*dimensions, len(traces)):
            raise ValueError('four-view dimensions/frame count mismatch: ' + view)
        decode = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                                 '-f', 'null', '-'], capture_output=True, text=True)
        if decode.returncode or decode.stderr.strip():
            raise ValueError('full video decode failed: ' + view)
        hashes[view] = sha(path)
    physical = evaluate(traces, case)
    if physical['physical_checks']['maneuver']['status'] != 'unverified':
        raise ValueError('synthetic diagnostic rows asserted physical completion')
    return {'case_id': case, 'source_frame_count': len(traces), 'decoded_views': list(VIEWS),
            'video_sha256': hashes, 'physical_completion': False,
            'physical_check': physical['physical_checks']['maneuver'],
            'legal_judgment': None, 'diagnostic_only': True}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', required=True)
    p.add_argument('--case', required=True)
    p.add_argument('--negative', action='store_true')
    args = p.parse_args()
    result = audit(args.attempt, args.case)
    if args.negative:
        raise ValueError('negative audit expected to reject damaged attempt')
    print(json.dumps(result, separators=(',', ':')))


if __name__ == '__main__':
    main()
