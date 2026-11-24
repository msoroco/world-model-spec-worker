"""Independent source and lifecycle audit for an original Native attempt.

This checks integrity and provenance. It does not determine physical or legal
acceptance; original pixels and roundabout geometry still need review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
REQUIRED = ('native-raw-actors.jsonl', 'roundabout-track.jsonl',
    'video_frames.jsonl', 'trace.jsonl', 'native-map-readback.json',
    'native-run-status.json', 'authored-road.xodr') + tuple(name + '.mkv' for name in CAMERAS)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def decode_cameras(root):
    for name in CAMERAS:
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
            '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(root / (name + '.mkv'))],
            capture_output=True, text=True, timeout=120)
        if probe.returncode or probe.stdout.strip() != '600':
            raise ValueError('Original source camera decode differs: ' + name)


def audit(attempt):
    root = Path(attempt).resolve()
    config = json.loads((root / 'config.json').read_text())
    seal = json.loads((root / 'capture-seal.json').read_text())
    provenance = json.loads((root / 'acquisition-provenance.json').read_text())
    status = json.loads((root / 'native-run-status.json').read_text())
    if (seal.get('provenance_kind') != 'native' or seal.get('diagnostic_fixture') is not False or
            provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is not False):
        raise ValueError('Original Native acquisition provenance required')
    if seal.get('frames') != 600 or status.get('frames') != 600 or status.get('errors'):
        raise ValueError('Complete error-free Native capture required')
    if (seal.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified'] or
            seal.get('restoration', {}).get('restored') is not True):
        raise ValueError('Native closure and restoration seal required')
    sources = seal.get('sources', {})
    for name in REQUIRED:
        path = root / name
        if not path.is_file() or sources.get(name) != sha(path):
            raise ValueError('Sealed original source differs: ' + name)
    if config['road_sha256'] != sha(root / 'authored-road.xodr'):
        raise ValueError('Authored OpenDRIVE source differs')
    route, raw, mapping = [rows(root / name) for name in
        ('roundabout-track.jsonl', 'native-raw-actors.jsonl', 'video_frames.jsonl')]
    if not (len(route) == len(raw) == len(mapping) == 600):
        raise ValueError('600 original source/frame joins required')
    last_native = -1
    for i, (point, actor, frame) in enumerate(zip(route, raw, mapping)):
        if (point.get('source_kind') != 'original_native' or
                actor.get('source_kind') != 'original_native' or
                point['frame'] != actor['frame'] or point['frame'] != i or
                frame['video_frame'] != i or
                point['native_frame'] != actor['native_frame'] or
                point['native_frame'] != frame['native_frame'] or
                point['native_frame'] <= last_native or
                abs(point['time_s'] - actor['time_s']) > 1e-6 or
                abs(point['time_s'] - frame['time_s']) > 1e-6 or
                point['observed_road_id'] != actor['observed_road_id'] or
                point['observed_lane_id'] != actor['observed_lane_id']):
            raise ValueError('Original Native source/frame join differs at ' + str(i))
        last_native = point['native_frame']
    decode_cameras(root)
    return {'format': 'c131364-native-source-audit-v2', 'case_id': config['case_id'],
        'source_verified': True, 'frames': 600, 'camera_count': 4,
        'sealed_original_sha256': sha(root / 'capture-seal.json'),
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt)))
