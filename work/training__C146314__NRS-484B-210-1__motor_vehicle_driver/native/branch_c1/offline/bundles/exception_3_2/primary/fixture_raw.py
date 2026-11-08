"""Raw-shaped synthetic CPU fixture; never an original Native observation."""
import argparse
import hashlib
import json
from pathlib import Path

from build import put, put_rows, sha


def actor(actor_id, x, y, vx, vy=0):
    corners = ((x-2, y-.9), (x-2, y+.9),
               (x+2, y+.9), (x+2, y-.9))
    return {'actor_id': actor_id, 'blueprint': 'vehicle.tesla.model3',
            'center_native_xyz_m': [x, y, 1.5], 'yaw_deg': 0,
            'velocity_native_xyz_mps': [vx, vy, 0],
            'speed_mps': round((vx*vx+vy*vy)**.5, 6),
            'body_native_xyz_m': [[round(px, 6), round(py, 6), z]
                                   for z in (.5, 2.5) for px, py in corners]}


def build(bundle, output):
    bundle, output = map(Path, (bundle, output))
    if output.exists():
        raise ValueError('raw output must be fresh')
    cfg = json.loads((bundle/'config.json').read_text())
    requests = [json.loads(line) for line in
                (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(requests) != 240:
        raise ValueError('request count')
    put(output/'native-map-readback.json', {
        'source_kind': 'synthetic_cpu',
        'road_sha256': sha(bundle/'unmarked-pass.xodr'),
        'native_map_sha256': hashlib.sha256(b'synthetic-c146314-road-212').hexdigest(),
        'driving_lane_readback': {str(n): {'road_id': 212, 'lane_id': n}
                                  for n in (-2, -1)},
        'ego_actor_id': 101, 'lead_actor_id': 102,
        'authored_shoulder_lane_readback': True,
        'pavement_condition_verified': False, 'legal_verdict': None})
    actors, videos, reviews = [], [], []
    for i, request in enumerate(requests):
        x, y, lx, t = (request[key] for key in
                       ('ego_x_m', 'ego_y_m', 'lead_x_m', 'time_s'))
        native = i+1000
        previous = requests[i-1] if i else request
        vx = round((x-previous['ego_x_m'])*20, 6)
        vy = round((y-previous['ego_y_m'])*20, 6)
        actors.append({'frame': i, 'native_frame': native, 'time_s': t,
                       'source_kind': 'synthetic_cpu',
                       'requested_ego_x_m': x, 'requested_ego_y_m': y,
                       'requested_lead_x_m': lx,
                       'observed_ego_road_id': 212,
                       'observed_ego_lane_id': -2 if y < -3.5 else -1,
                       'observed_lead_road_id': 212, 'observed_lead_lane_id': -1,
                       'ego': actor(101, x, y, vx, vy),
                       'lead': actor(102, lx, -1.75, 4),
                       'requested_lead_left_signal': False,
                       'observed_lead_light_state': 0,
                       'observed_lead_left_blinker': False,
                       'authored_shoulder_lane_readback': True,
                       'pavement_condition_verified': False, 'legal_verdict': None})
        videos.append({'video_frame': i, 'native_frame': native, 'time_s': t})
        reviews.append({'frame': i, 'native_frame': native, 'time_s': t,
                        'source_kind': 'synthetic_cpu',
                        'review_provenance': 'synthetic_cpu',
                        'forward_video_sha256': 'synthetic_cpu',
                        'overview_video_sha256': 'synthetic_cpu',
                        'boundary_pixel_reviewed': False,
                        'pavement_pixel_reviewed': False,
                        'unmarked_pavement_visible': None})
    put_rows(output/'native-raw-actors.jsonl', actors)
    put_rows(output/'video_frames.jsonl', videos)
    put_rows(output/'frame-review.jsonl', reviews)
    put(output/'native-capture-report.json', {
        'case_id': cfg['case_id'], 'candidate_id': cfg['candidate_id'],
        'config_sha256': sha(bundle/'config.json'),
        'requested_frames': 240, 'observed_frames': 240,
        'restoration': {'synthetic_cpu': True}, 'error': None,
        'accepted': False, 'authored_shoulder_lane_readback': True,
        'pavement_condition_verified': False, 'legal_verdict': None,
        'delivery_ready': False})
    return {'source_kind': 'synthetic_cpu', 'frames': 240}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(build(a.bundle, a.output_dir)))
