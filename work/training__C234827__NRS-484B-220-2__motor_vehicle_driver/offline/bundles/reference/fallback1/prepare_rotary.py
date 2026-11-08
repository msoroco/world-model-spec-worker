"""Prepare exact rotary saved inputs from Native capture and frame review."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure_saved import FILES, measure

RAW = ('native-raw-ego.jsonl', 'native-map-readback.json', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def verify_video(path):
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
            '-select_streams', 'v:0', '-show_entries',
            'stream=codec_name,nb_read_frames', '-of', 'json', str(path)],
            capture_output=True, text=True, check=True, timeout=180)
        streams = json.loads(result.stdout)['streams']
        if len(streams) != 1 or streams[0].get('codec_name') != 'ffv1' or int(
                streams[0].get('nb_read_frames', 0)) != 240:
            raise ValueError('Rotary forward video codec or frame count differs')
    except (OSError, subprocess.CalledProcessError, KeyError, TypeError,
            json.JSONDecodeError) as error:
        raise ValueError('Rotary forward FFV1 video could not be verified') from error


def prepare(raw_folder, review_path, config_path, output):
    raw_folder, review_path, config_path, output = map(Path,
        (raw_folder, review_path, config_path, output))
    if output.exists():
        raise ValueError('Rotary saved destination must be fresh')
    config = json.loads(config_path.read_text())
    if (config.get('format') != 'c234827-native-request-v1' or
            config.get('status') != 'unselected_native_request' or
            config.get('island_side_request') not in ('reference', 'contrast') or
            config.get('frames') != 240 or config.get('rate_hz') != 20):
        raise ValueError('Rotary case configuration differs')
    paths = {name: raw_folder/name for name in RAW}
    video = raw_folder/'forward.mkv' if (raw_folder/'forward.mkv').is_file() else raw_folder/'forward-video-stub.txt'
    paths['forward_video'] = video
    if any(not path.is_file() for path in paths.values()) or not review_path.is_file():
        raise ValueError('Rotary raw or review source absent')
    hashes = {name: sha(path) for name, path in paths.items()}
    review = json.loads(review_path.read_text())
    mapping = json.loads(paths['native-map-readback.json'].read_text())
    if (review.get('format') != 'c234827-island-frame-review-v1' or
            review.get('source_hashes') != hashes or
            not isinstance(review.get('rows'), list) or len(review['rows']) != 240 or
            mapping.get('road_sha256') != config.get('road_sha256') or
            mapping.get('island_geometry_sha256') != config.get('island_geometry_sha256') or
            mapping.get('center_xy_m') != [0, 0] or
            mapping.get('island_radius_m') != 15 or
            mapping.get('driving_lane_ids') != [-2, -1] or
            mapping.get('physical_island_verified') is not False or
            mapping.get('traffic_control_verified') is not False or
            not isinstance(mapping.get('native_map_sha256'), str) or
            len(mapping['native_map_sha256']) != 64):
        raise ValueError('Rotary map or frame-review source binding differs')
    raw = lines(paths['native-raw-ego.jsonl'])
    frames = lines(paths['video_frames.jsonl'])
    if len(raw) != 240 or len(frames) != 240:
        raise ValueError('Rotary raw/video frame coverage differs')
    kind = raw[0].get('source_kind')
    if kind not in ('synthetic_cpu', 'original_native') or review.get('source_kind') != kind:
        raise ValueError('Rotary source provenance differs')
    if kind == 'original_native':
        if video.name != 'forward.mkv' or review.get('review_provenance') != 'human_frame_review':
            raise ValueError('Original rotary forward review absent')
        verify_video(video)
    elif review.get('review_provenance') != 'synthetic_cpu':
        raise ValueError('Synthetic rotary review provenance differs')
    first_native = raw[0].get('native_frame')
    first_time = raw[0].get('time_s')
    if type(first_native) is not int or not finite(first_time):
        raise ValueError('Rotary initial Native frame/time differs')
    observed, island_frames = [], []
    actor_id = None
    case = config['island_side_request']
    for i, (row, frame, sight) in enumerate(zip(raw, frames, review['rows'])):
        if (row.get('frame') != i or row.get('native_frame') != first_native+i or
                row.get('source_kind') != kind or row.get('case') != case or
                not finite(row.get('time_s')) or
                abs(row['time_s']-first_time-i/20) > 1e-4 or
                frame.get('video_frame') != i or frame.get('native_frame') != row['native_frame'] or
                not finite(frame.get('time_s')) or abs(frame['time_s']-row['time_s']) > 1e-4 or
                sight.get('frame') != i or sight.get('native_frame') != row['native_frame'] or
                sight.get('camera_frame') != row['native_frame'] or
                not finite(sight.get('time_s')) or abs(sight['time_s']-row['time_s']) > 1e-4 or
                type(sight.get('island_visible')) is not bool or
                row.get('native_lane_id') not in (-2, -1)):
            raise ValueError('Rotary raw, video or frame-review join differs')
        ego = row.get('ego')
        if not isinstance(ego, dict) or ego.get('blueprint') != 'vehicle.tesla.model3':
            raise ValueError('Rotary Native ego blueprint differs')
        if actor_id is None:
            actor_id = ego.get('actor_id')
        if type(actor_id) is not int or ego.get('actor_id') != actor_id:
            raise ValueError('Rotary Native ego identity differs')
        center = ego.get('center_native_xyz_m')
        velocity = ego.get('velocity_native_xyz_mps')
        body = ego.get('body_native_xyz_m')
        if (not isinstance(center, list) or len(center) != 3 or
                not isinstance(velocity, list) or len(velocity) != 3 or
                not all(finite(value) for value in center+velocity) or
                not isinstance(body, list) or len(body) < 4 or
                any(not isinstance(point, list) or len(point) != 3 or
                    not all(finite(value) for value in point) for point in body) or
                not finite(ego.get('yaw_deg')) or not finite(ego.get('speed_mps')) or
                abs(ego['speed_mps']-math.sqrt(sum(value*value for value in velocity))) > .1):
            raise ValueError('Rotary Native ego pose, body or velocity differs')
        saved = {'frame': i, 'time_s': (i+1)/20,
                 'native_frame': row['native_frame'], 'source_kind': kind, 'case': case,
                 'ego_x_m': center[0], 'ego_y_m': -center[1],
                 'ego_heading_deg': (-ego['yaw_deg'])%360,
                 'ego_speed_mps': ego['speed_mps'], 'lane_id': row['native_lane_id'],
                 'ego_body_xy_m': [[point[0], -point[1]] for point in body]}
        if kind == 'original_native':
            saved.update(ego_actor_id=actor_id, ego_blueprint=ego['blueprint'])
        observed.append(saved)
        island_frames.append({'frame': i, 'native_frame': row['native_frame'],
            'camera_frame': sight['camera_frame'], 'time_s': (i+1)/20,
            'source_kind': kind, 'island_visible': sight['island_visible']})
    output.mkdir(parents=True)
    def write(name, value):
        (output/name).write_text(json.dumps(value, indent=2)+'\n')
    for name, rows in (('native-observed.jsonl', observed),
                       ('island-frames.jsonl', island_frames)):
        (output/name).write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))
    write('island-readback.json', {'source_kind': kind, 'center_xy_m': [0, 0],
        'island_radius_m': 15, 'driving_lane_ids': [-2, -1],
        'road_sha256': config['road_sha256'],
        'native_map_sha256': mapping['native_map_sha256'],
        'raw_source_hashes': hashes, 'review_sha256': sha(review_path),
        'physical_island_verified': False, 'traffic_control_verified': False,
        'review_provenance': review['review_provenance']})
    measured = measure(output)
    receipt = {'format': 'c234827-prepared-saved-rotary-v1',
        'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
        'source_kind': kind, 'raw_source_hashes': hashes,
        'review_sha256': sha(review_path), 'config_sha256': sha(config_path),
        'saved_hashes': {name: sha(output/name) for name in FILES},
        'measurement': measured, 'physical_island_verified': False,
        'traffic_control_verified': False, 'legal_verdict': None,
        'delivery_ready': False}
    write('preparation-receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-folder', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.raw_folder, args.review, args.config, args.output), indent=2))
