"""Raw-shaped synthetic CPU fixture; never original Native evidence."""
import argparse
import hashlib
import json
from pathlib import Path

from check import check


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def write_rows(path, values):
    path.write_text(''.join(json.dumps(value, allow_nan=False) + '\n' for value in values))


def body(x, y):
    return [[x+dx, y+dy, z] for dx in (-2.2, 2.2)
            for dy in (-.9, .9) for z in (.2, 1.6)]


def build(bundle, output):
    bundle, output = map(Path, (bundle, output))
    checked = check(bundle)
    cfg = json.loads((bundle / 'config.json').read_text())
    requests = [json.loads(line) for line in
                (bundle / 'requested-tracks.jsonl').read_text().splitlines()]
    output.mkdir(parents=True, exist_ok=False)
    put(output / 'native-map-readback.json', {
        'source_kind': 'synthetic_cpu',
        'road_sha256': sha(bundle / 'alley-stop.xodr'),
        'native_map_sha256': '1' * 64,
        'lane_readback': {str(x): {'road_id': 389, 'lane_id': -1,
                                  'lane_type': 'driving'} for x in (20, 45, 55)},
        'stop_landmark_readback': {'id': '3891', 'road_id': 389,
                                   's_m': 50.0, 'type': '206'},
        'stop_landmark_verified': True, 'ego_actor_id': 101,
        'official_placement_verified': False,
        'police_direction_verified': False,
        'signal_specific_exception_reviewed': False,
        'legal_verdict': None})
    actors, videos, reviews = [], [], []
    for i, request in enumerate(requests):
        x = request['requested_ego_x_m']
        speed = request['requested_speed_mps']
        native = 1000+i
        t = request['time_s']
        actors.append({'frame': i, 'native_frame': native, 'time_s': t,
            'source_kind': 'synthetic_cpu', 'requested_ego_x_m': x,
            'requested_speed_mps': speed,
            'ego': {'actor_id': 101, 'blueprint': 'vehicle.tesla.model3',
                    'center_native_xyz_m': [x, -1.75, 1],
                    'velocity_native_xyz_mps': [speed, 0, 0],
                    'speed_mps': speed, 'body_native_xyz_m': body(x, -1.75)},
            'observed_road_id': 389, 'observed_lane_id': -1,
            'official_placement_verified': False,
            'police_direction_verified': False,
            'observed_device_obedience': None, 'legal_verdict': None})
        videos.append({'video_frame': i, 'native_frame': native, 'time_s': t})
        reviews.append({'frame': i, 'native_frame': native, 'time_s': t,
            'source_kind': 'synthetic_cpu', 'review_provenance': 'synthetic_cpu',
            'forward_video_sha256': 'synthetic_cpu',
            'overview_video_sha256': 'synthetic_cpu',
            'device_face_pixel_reviewed': True, 'device_face_visible': True,
            'approach_area_pixel_reviewed': True, 'approach_area_visible': True})
    write_rows(output / 'native-raw-actors.jsonl', actors)
    write_rows(output / 'video_frames.jsonl', videos)
    write_rows(output / 'frame-review.jsonl', reviews)
    put(output / 'native-capture-report.json', {
        'case_id': checked['case_id'], 'candidate_id': checked['candidate_id'],
        'config_sha256': sha(bundle / 'config.json'),
        'requested_frames': 240, 'observed_frames': 240,
        'error': None, 'accepted': False, 'delivery_ready': False,
        'stop_landmark_verified': True,
        'official_placement_verified': False,
        'police_direction_verified': False, 'legal_verdict': None})
    return {'source_kind': 'synthetic_cpu', 'rows': 240, 'delivery_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.bundle, args.output_dir)))
