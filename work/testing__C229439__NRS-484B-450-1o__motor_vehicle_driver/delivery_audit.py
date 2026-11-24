"""Independent CPU acceptance preflight for source-sealed four-view attempts.

Diagnostic attempts exercise software gates only. Physical and legal acceptance
requires later original CARLA capture and independent source review.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

VIEWS = {'overview': (1920, 1080), 'approach': (1280, 720),
         'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root, case):
    root = Path(root).resolve()
    config = json.loads((root / 'config.json').read_text())
    attempt = json.loads((root / 'attempt.json').read_text())
    if config['case']['case_id'] != case or attempt['case_id'] != case:
        raise ValueError('exact case identity mismatch')
    for source in ('site-source.json', 'device-source.json', 'actor_rows.json'):
        if not (root / source).is_file():
            raise ValueError('Missing required source: ' + source)
    rows = json.loads((root / 'actor_rows.json').read_text())
    if len(rows) != 900 or [row['frame'] for row in rows] != list(range(1, 901)):
        raise ValueError('full original frame history required')
    if len({row['subject_id'] for row in rows}) != 1 or any(row['case_id'] != case for row in rows):
        raise ValueError('participant identity/time join mismatch')
    frame_map = (root / 'video_frames.jsonl').read_text().splitlines()
    if len(frame_map) != 900:
        raise ValueError('four-view frame map incomplete')
    for index, row in enumerate(rows):
        frame = json.loads(frame_map[index])
        if frame.get('native_frame') != row['frame'] or frame.get('video_frame') != index or abs(frame.get('time_s', -1) - row['time_s']) > 0.001 or abs(row['time_s'] - index / 20) > 0.001:
            raise ValueError('source/video frame time join mismatch')
    video_hashes = {}
    for view, dimensions in VIEWS.items():
        path = root / (view + '.mkv')
        if not path.is_file():
            raise ValueError('Missing original camera: ' + view)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                '-count_frames', '-show_entries',
                                'stream=width,height,nb_read_frames', '-of', 'json', str(path)],
                               capture_output=True, text=True, check=True)
        stream = json.loads(probe.stdout)['streams'][0]
        if (stream['width'], stream['height'], int(stream['nb_read_frames'])) != (*dimensions, 900):
            raise ValueError('four-view dimensions or frame count mismatch: ' + view)
        decode = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                                 '-f', 'null', '-'], capture_output=True, text=True)
        if decode.returncode or decode.stderr.strip():
            raise ValueError('full video decode failed: ' + view + ' ' + decode.stderr[-300:])
        video_hashes[view] = _sha(path)
    return {'case_id': case, 'source_frame_count': 900, 'decoded_views': list(VIEWS),
            'video_sha256': video_hashes, 'physical_completion': False,
            'legal_judgment': None, 'diagnostic_only': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    result = audit(args.attempt, args.case)
    if args.negative:
        raise ValueError('negative audit expected to reject a damaged attempt')
    print(json.dumps(result, separators=(',', ':')))


if __name__ == '__main__':
    main()
