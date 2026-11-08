"""Join raw Native actors and reviewed sightlines into saved pass observations."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure_pass import measure

HERE = Path(__file__).resolve().parent
REQUIRED = ('native-raw-actors.jsonl', 'native-map-readback.json',
            'video_frames.jsonl')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def actor(row, name, actor_id, source_kind):
    value = row.get(name)
    if not isinstance(value, dict) or value.get('actor_id') != actor_id:
        raise ValueError('Raw actor identity differs: '+name)
    if value.get('blueprint') != ('vehicle.tesla.model3' if name == 'ego' else 'vehicle.audi.tt'):
        raise ValueError('Raw actor blueprint differs: '+name)
    center = value.get('center_native_xyz_m')
    velocity = value.get('velocity_native_xyz_mps')
    body = value.get('body_native_xyz_m')
    if (not isinstance(center, list) or len(center) != 3 or
            not isinstance(velocity, list) or len(velocity) != 3 or
            not all(number(v) for v in center+velocity) or
            not isinstance(body, list) or len(body) < 4 or
            any(not isinstance(point, list) or len(point) != 3 or
                not all(number(v) for v in point) for point in body)):
        raise ValueError('Raw actor pose, velocity or body differs: '+name)
    if name == 'oncoming' and velocity[0] >= 0 or name != 'oncoming' and velocity[0] <= 0:
        raise ValueError('Raw actor direction differs: '+name)
    x, y = center[0], -center[1]
    points = [[point[0], -point[1]] for point in body]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    if not min(xs) <= x <= max(xs) or not min(ys) <= y <= max(ys):
        raise ValueError('Raw actor center outside body: '+name)
    speed = value.get('speed_mps')
    if not number(speed) or speed < 0 or abs(speed-math.sqrt(sum(v*v for v in velocity))) > .1:
        raise ValueError('Raw actor speed and velocity differ: '+name)
    return x, y, speed, points


def prepare(raw_folder, review_path, output, config_path):
    raw_folder, review_path, output, config_path = map(Path,
                                                        (raw_folder, review_path, output, config_path))
    if output.exists():
        raise ValueError('Saved pass destination must be fresh')
    config = json.loads(config_path.read_text())
    if (config.get('format') != 'c102951-native-request-v1' or
            config.get('status') != 'unselected_native_request' or
            config.get('candidate_id') == 'fallback3'):
        raise ValueError('Only completed-pass candidates use this processor')
    paths = {name: raw_folder/name for name in REQUIRED}
    video = raw_folder/'forward.mkv' if (raw_folder/'forward.mkv').exists() else raw_folder/'forward-video-stub.txt'
    paths['forward_video'] = video
    if any(not path.is_file() for path in paths.values()):
        raise ValueError('Raw actor, map or synchronized video source absent')
    source_hashes = {name: sha(path) for name, path in paths.items()}
    review = json.loads(review_path.read_text())
    if (review.get('format') != 'c102951-sightline-review-v1' or
            review.get('source_hashes') != source_hashes or
            not isinstance(review.get('rows'), list) or len(review['rows']) != 480):
        raise ValueError('Sightline review source binding or coverage differs')
    map_info = json.loads(paths['native-map-readback.json'].read_text())
    if (map_info.get('road_sha256') != config.get('road_sha256') or
            not isinstance(map_info.get('native_map_sha256'), str) or
            len(map_info['native_map_sha256']) != 64 or
            any(c not in '0123456789abcdef' for c in map_info['native_map_sha256']) or
            map_info.get('right_lane_id') == map_info.get('opposing_lane_id') or
            any(type(map_info.get(k)) is not int for k in
                ('right_lane_id', 'opposing_lane_id', 'ego_actor_id',
                 'overtaken_actor_id', 'oncoming_actor_id')) or
            map_info.get('highway_status_reviewed') is not False):
        raise ValueError('Native two-direction map readback differs')
    raw = [json.loads(line) for line in paths['native-raw-actors.jsonl'].read_text().splitlines()]
    frames = [json.loads(line) for line in paths['video_frames.jsonl'].read_text().splitlines()]
    if len(raw) != 480 or len(frames) != 480:
        raise ValueError('Raw actor/video frame coverage differs')
    source_kind = raw[0].get('source_kind')
    if source_kind not in ('synthetic_cpu', 'original_native') or review.get('source_kind') != source_kind:
        raise ValueError('Raw/review provenance differs')
    if source_kind == 'original_native':
        if video.name != 'forward.mkv' or review.get('review_provenance') != 'human_frame_review':
            raise ValueError('Original Native video or manual sightline review absent')
        try:
            probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                    '-select_streams', 'v:0', '-show_entries',
                                    'stream=codec_name,nb_read_frames', '-of', 'json',
                                    str(video)], capture_output=True, text=True,
                                   timeout=180, check=True)
            streams = json.loads(probe.stdout)['streams']
            if len(streams) != 1 or streams[0].get('codec_name') != 'ffv1' or int(
                    streams[0].get('nb_read_frames', 0)) != 480:
                raise ValueError('Original forward video codec or 480-frame coverage differs')
        except (OSError, subprocess.CalledProcessError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError('Original forward FFV1 video could not be verified') from error
    elif review.get('review_provenance') != 'synthetic_cpu':
        raise ValueError('Synthetic review provenance differs')
    if config['distance_m'] not in (70, 120, 170):
        raise ValueError('Frozen clear-distance case differs')
    first_native = raw[0].get('native_frame')
    first_time = raw[0].get('time_s')
    if type(first_native) is not int or not number(first_time):
        raise ValueError('Raw initial Native frame/time differs')
    saved = []
    for i, (row, frame, sight) in enumerate(zip(raw, frames, review['rows'])):
        if (row.get('frame') != i or row.get('native_frame') != first_native+i or
                row.get('source_kind') != source_kind or not number(row.get('time_s')) or
                abs(row['time_s']-first_time-i/20) > 1e-4 or
                frame.get('video_frame') != i or frame.get('native_frame') != row['native_frame'] or
                not number(frame.get('time_s')) or abs(frame['time_s']-row['time_s']) > 1e-4 or
                sight.get('frame') != i or sight.get('native_frame') != row['native_frame'] or
                not number(sight.get('time_s')) or abs(sight['time_s']-row['time_s']) > 1e-4 or
                type(sight.get('sightline_visible')) is not bool or
                not number(sight.get('driver_eye_clear_m')) or sight['driver_eye_clear_m'] < 0):
            raise ValueError('Raw actor/video/sightline frame join differs')
        record = {'frame': i, 'native_frame': row['native_frame'],
                  'time_s': row['time_s'], 'source_kind': source_kind,
                  'ego_blueprint': 'vehicle.tesla.model3',
                  'sightline_visible': sight['sightline_visible'],
                  'driver_eye_clear_m': sight['driver_eye_clear_m']}
        for name in ('ego', 'overtaken', 'oncoming'):
            x, y, speed, body = actor(row, name, map_info[name+'_actor_id'], source_kind)
            record[name+'_x_m'] = x
            record[name+'_y_m'] = y
            record[name+'_speed_mps'] = speed
            if source_kind == 'original_native':
                record[name+'_body_xy_m'] = body
        saved.append(record)
    output.mkdir(parents=True)
    (output/'native-observed.jsonl').write_text(''.join(json.dumps(row, sort_keys=True)+'\n'
                                                         for row in saved))
    road = {'format': 'c102951-road-readback-v1', 'lane_count': 2,
            'travel_directions': 2, 'centerline_y_m': 0,
            'crest_profile': 'source_bound_native_map_readback',
            'highway_status_reviewed': False,
            'source_kind': source_kind,
            'road_sha256': config['road_sha256'],
            'native_map_sha256': map_info.get('native_map_sha256'),
            'source_hashes': source_hashes,
            'sightline_review_sha256': sha(review_path),
            'config_sha256': sha(config_path)}
    (output/'road-readback.json').write_text(json.dumps(road, indent=2)+'\n')
    metric = measure(output)
    receipt = {'format': 'c102951-prepared-saved-pass-v1',
               'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
               'source_kind': source_kind, 'source_hashes': source_hashes,
               'sightline_review_sha256': sha(review_path),
               'config_sha256': sha(config_path),
               'saved_hashes': {name: sha(output/name) for name in
                                ('native-observed.jsonl', 'road-readback.json')},
               'measurement': metric, 'original_highway_status_reviewed': False,
               'safe_distance_judgment': None, 'interference_judgment': None,
               'legal_verdict': None, 'delivery_ready': False}
    (output/'preparation-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-folder', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.raw_folder, args.review, args.output, args.config), indent=2))
