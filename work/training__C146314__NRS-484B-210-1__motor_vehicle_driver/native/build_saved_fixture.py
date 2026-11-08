"""Create explicitly synthetic C146314 observed-shape controls for saved processing."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def put(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def put_rows(path, items):
    Path(path).write_text(''.join(json.dumps(x, sort_keys=True, allow_nan=False)+'\n'
                                  for x in items))


def body(x, y):
    return [[round(x + dx, 6), round(y + dy, 6)]
            for dx, dy in ((-2.3, -1), (-2.3, 1), (2.3, 1), (2.3, -1))]


def build(bundle, output):
    bundle, output = Path(bundle), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    cfg = json.loads((bundle/'config.json').read_text())
    request = rows(bundle/'requested-tracks.jsonl')
    observed, cameras = [], []
    for i, req in enumerate(request):
        observed.append({'frame': i, 'native_frame': 1000+i,
            'time_s': req['time_s'], 'source_kind': 'synthetic_cpu',
            'road_id': 210, 'ego_actor_id': 1, 'lead_actor_id': 2,
            'obstruction_actor_id': 3 if cfg['right_lane_obstruction_requested'] else None,
            'ego_x_m': req['ego_x_m'], 'ego_y_m': req['ego_y_m'],
            'ego_body_xy_m': body(req['ego_x_m'], req['ego_y_m']),
            'ego_lane_id': req['ego_lane_id'],
            'lead_x_m': req['lead_x_m'], 'lead_y_m': req['lead_y_m'],
            'lead_body_xy_m': body(req['lead_x_m'], req['lead_y_m']),
            'lead_lane_id': -1,
            'obstruction_x_m': cfg['obstruction_x_m'],
            'obstruction_y_m': cfg['obstruction_y_m'],
            'obstruction_radius_m': cfg['obstruction_radius_m'],
            'one_way_designation_verified': False,
            'pavement_condition_verified': False,
            'legal_verdict': None})
        cameras.append({'frame': i, 'native_frame': 1000+i,
            'time_s': req['time_s'], 'source_kind': 'synthetic_cpu',
            'forward_frame': i, 'overview_frame': i,
            'object_pixel_reviewed': False,
            'lane_pixel_reviewed': False})
    put_rows(output/'native-observed.jsonl', observed)
    put_rows(output/'camera-frames.jsonl', cameras)
    put(output/'readback.json', {'source_kind': 'synthetic_cpu',
        'road_sha256': cfg['road_sha256'], 'config_sha256': sha(bundle/'config.json'),
        'tracks_sha256': cfg['tracks_sha256'],
        'observed_sha256': sha(output/'native-observed.jsonl'),
        'camera_sha256': sha(output/'camera-frames.jsonl'),
        'one_way_designation_verified': False,
        'pavement_condition_verified': False,
        'object_pixel_reviewed': False, 'legal_verdict': None})
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args()
    print(build(a.bundle, a.output_dir))
