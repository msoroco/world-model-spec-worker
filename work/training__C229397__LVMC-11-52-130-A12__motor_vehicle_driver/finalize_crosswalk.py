"""Fail-closed saved-only join and crosswalk distance diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path

from crosswalk_measure import ASSIGNMENT, FRAMES, measure
from source_review import join

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def finalize(attempt):
    attempt = Path(attempt)
    source_paths = [attempt / name for name in ('vehicle-poses.jsonl', 'video_frames.jsonl', 'crosswalk-inventory.json', 'control-intent.jsonl')]
    if not all(p.is_file() for p in source_paths):
        raise ValueError('required original saved source missing')
    poses = _jsonl(source_paths[0])
    frame_map = _jsonl(source_paths[1])
    controls = _jsonl(source_paths[3])
    if len(poses) != FRAMES or len(frame_map) != FRAMES or len(controls) != FRAMES:
        raise ValueError('600 original saved frames required')
    for i, (pose, frame, control) in enumerate(zip(poses, frame_map, controls)):
        if pose.get('video_frame') != i or frame.get('video_frame') != i or pose.get('native_frame') != frame.get('native_frame'):
            raise ValueError('original pose/frame-map identity join failed')
        if abs(pose.get('time_s', -1) - frame.get('time_s', -2)) > .005:
            raise ValueError('original pose/frame-map timing join failed')
        if (control.get('video_frame') != i or control.get('native_frame') != pose['native_frame'] or
                control.get('vehicle_id') != pose.get('vehicle_id') or
                abs(control.get('time_s', -1) - pose['time_s']) > .005):
            raise ValueError('original control/pose identity join failed')
        camera_frames = frame.get('camera_native_frames')
        if not isinstance(camera_frames, dict) or set(camera_frames) != set(CAMERAS) or any(camera_frames[name] != pose['native_frame'] for name in CAMERAS):
            raise ValueError('four original camera identities missing or mismatched')
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': 'native_saved_sample',
              'vehicle_id': poses[0]['vehicle_id'], 'frames': poses}
    packet_bytes = json.dumps(packet, sort_keys=True, separators=(',', ':')).encode()
    inventory, review_sha, review_findings = join(attempt, json.loads(source_paths[2].read_bytes()))
    diagnostic = measure(packet_bytes, json.dumps(inventory, sort_keys=True).encode())
    diagnostic['original_source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    diagnostic['independent_source_review_sha256'] = review_sha
    diagnostic['independent_source_review_findings'] = review_findings
    diagnostic['camera_frame_map_validated'] = True
    diagnostic['engineering_action'] = controls[0].get('engineering_action')
    diagnostic['control_frame_join_validated'] = True
    diagnostic['video_pixels_decoded'] = False
    return diagnostic


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt), sort_keys=True))
