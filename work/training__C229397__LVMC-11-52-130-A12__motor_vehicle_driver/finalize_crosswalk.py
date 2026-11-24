"""Fail-closed saved-only join and crosswalk distance diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path

from crosswalk_measure import ASSIGNMENT, FRAMES, measure

CAMERAS = ('overview', 'crosswalk', 'parking_approach', 'subject_side')


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def finalize(attempt):
    attempt = Path(attempt)
    source_paths = [attempt / name for name in ('vehicle-poses.jsonl', 'video_frames.jsonl', 'crosswalk-inventory.json')]
    if not all(p.is_file() for p in source_paths):
        raise ValueError('required original saved source missing')
    poses = _jsonl(source_paths[0])
    frame_map = _jsonl(source_paths[1])
    if len(poses) != FRAMES or len(frame_map) != FRAMES:
        raise ValueError('600 original saved frames required')
    for i, (pose, frame) in enumerate(zip(poses, frame_map)):
        if pose.get('video_frame') != i or frame.get('video_frame') != i or pose.get('native_frame') != frame.get('native_frame'):
            raise ValueError('original pose/frame-map identity join failed')
        if abs(pose.get('time_s', -1) - frame.get('time_s', -2)) > .005:
            raise ValueError('original pose/frame-map timing join failed')
        camera_frames = frame.get('camera_native_frames')
        if not isinstance(camera_frames, dict) or set(camera_frames) != set(CAMERAS) or any(camera_frames[name] != pose['native_frame'] for name in CAMERAS):
            raise ValueError('four original camera identities missing or mismatched')
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': 'native_saved_sample',
              'vehicle_id': poses[0]['vehicle_id'], 'frames': poses}
    packet_bytes = json.dumps(packet, sort_keys=True, separators=(',', ':')).encode()
    diagnostic = measure(packet_bytes, source_paths[2].read_bytes())
    diagnostic['original_source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    diagnostic['camera_frame_map_validated'] = True
    diagnostic['video_pixels_decoded'] = False
    return diagnostic


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt), sort_keys=True))
