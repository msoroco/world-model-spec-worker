"""Prepare source-bound C10389 Native rows and measure device station behavior."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from check import check

RAW = ('native-map-readback.json', 'native-raw-actors.jsonl',
       'video_frames.jsonl', 'frame-review.jsonl', 'native-capture-report.json')
SAVED = ('native-observed.jsonl', 'camera-frames.jsonl', 'frame-review.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def media(raw, synthetic):
    if synthetic:
        return {}
    result = {}
    for name in ('forward.mkv', 'overview.mkv'):
        result[name] = sha(raw / name)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
            '-select_streams', 'v:0', '-show_entries', 'stream=codec_name,nb_read_frames',
            '-of', 'json', str(raw / name)], capture_output=True, text=True,
            check=True, timeout=120)
        streams = json.loads(probe.stdout).get('streams', [])
        require(len(streams) == 1 and streams[0].get('codec_name') == 'ffv1' and
                streams[0].get('nb_read_frames') == '240', 'original 240-frame FFV1 media')
    return result


def validate_ego(ego, actor_id):
    require(type(ego) is dict and ego.get('actor_id') == actor_id and
            ego.get('blueprint') == 'vehicle.tesla.model3', 'ego identity')
    center = ego.get('center_native_xyz_m')
    velocity = ego.get('velocity_native_xyz_mps')
    body = ego.get('body_native_xyz_m')
    require(type(center) is list and len(center) == 3 and all(map(finite, center)) and
            type(velocity) is list and len(velocity) == 3 and all(map(finite, velocity)) and
            finite(ego.get('speed_mps')) and ego['speed_mps'] >= 0 and
            abs(math.sqrt(sum(v*v for v in velocity))-ego['speed_mps']) < .01 and
            type(body) is list and len(body) == 8 and
            all(type(p) is list and len(p) == 3 and all(map(finite, p)) for p in body),
            'finite ego body and speed')
    xs = [p[0] for p in body]
    ys = [p[1] for p in body]
    require(3 <= max(xs)-min(xs) <= 7 and 1.3 <= max(ys)-min(ys) <= 7 and
            abs((max(xs)+min(xs))/2-center[0]) < 1 and
            abs((max(ys)+min(ys))/2-center[1]) < 1, 'ego body geometry')


def prepare(bundle, raw, output, synthetic=False):
    bundle, raw, output = map(Path, (bundle, raw, output))
    checked = check(bundle)
    cfg = read(bundle / 'config.json')
    require(not output.exists(), 'saved output must be fresh')
    hashes = {name: sha(raw / name) for name in RAW}
    mapping, report = read(raw / RAW[0]), read(raw / RAW[-1])
    actors, videos, reviews = (rows(raw / name) for name in RAW[1:4])
    requests = rows(bundle / 'requested-tracks.jsonl')
    kind = 'synthetic_cpu' if synthetic else 'original_native'
    require(len(actors) == len(videos) == len(reviews) == len(requests) == 240,
            '240 raw joins')
    landmark = mapping.get('stop_landmark_readback')
    require(type(landmark) is dict and landmark.get('id') == '3891' and
            landmark.get('road_id') == 389 and
            finite(landmark.get('s_m')) and abs(landmark['s_m']-50) < .5 and
            landmark.get('type') == '206', 'generated stop landmark')
    require(mapping.get('source_kind') == kind and
            mapping.get('road_sha256') == sha(bundle / 'alley-stop.xodr') and
            type(mapping.get('native_map_sha256')) is str and
            len(mapping['native_map_sha256']) == 64 and
            mapping.get('lane_readback') == {str(x): {
                'road_id': 389, 'lane_id': -1, 'lane_type': 'driving'}
                for x in (20, 45, 55)} and
            mapping.get('stop_landmark_verified') is True and
            type(mapping.get('ego_actor_id')) is int and
            mapping.get('official_placement_verified') is False and
            mapping.get('police_direction_verified') is False and
            mapping.get('signal_specific_exception_reviewed') is False and
            mapping.get('legal_verdict') is None,
            'generated road and unverified device binding')
    require(report.get('case_id') == checked['case_id'] and
            report.get('candidate_id') == checked['candidate_id'] and
            report.get('config_sha256') == sha(bundle / 'config.json') and
            report.get('requested_frames') == report.get('observed_frames') == 240 and
            report.get('error') is None and report.get('accepted') is False and
            report.get('delivery_ready') is False and
            report.get('stop_landmark_verified') is True and
            report.get('official_placement_verified') is False and
            report.get('police_direction_verified') is False and
            report.get('legal_verdict') is None,
            'unaccepted capture report')
    media_hashes = media(raw, synthetic)
    first = actors[0].get('native_frame')
    require(type(first) is int, 'first native frame')
    observed, camera = [], []
    previous_center = None
    for i, (row, video, review, request) in enumerate(
            zip(actors, videos, reviews, requests)):
        native = first+i
        t = row.get('time_s')
        require(row.get('frame') == i and row.get('native_frame') == native and
                row.get('source_kind') == kind and finite(t) and
                abs(t-(i+1)/20) < .005 and
                row.get('requested_ego_x_m') == request['requested_ego_x_m'] and
                row.get('requested_speed_mps') == request['requested_speed_mps'] and
                row.get('observed_road_id') == 389 and
                row.get('observed_lane_id') == -1 and
                row.get('official_placement_verified') is False and
                row.get('police_direction_verified') is False and
                row.get('observed_device_obedience') is None and
                row.get('legal_verdict') is None, f'actor/request join {i}')
        validate_ego(row.get('ego'), mapping['ego_actor_id'])
        center = row['ego']['center_native_xyz_m']
        if previous_center is not None:
            displacement = math.sqrt(sum((center[j]-previous_center[j])**2
                                         for j in range(3)))
            require(displacement <= row['ego']['speed_mps'] / 20 + .5,
                    f'ego speed/displacement continuity {i}')
        previous_center = center
        require(video.get('video_frame') == i and
                video.get('native_frame') == native and
                finite(video.get('time_s')) and abs(video['time_s']-t) < 1e-6 and
                review.get('frame') == i and
                review.get('native_frame') == native and
                finite(review.get('time_s')) and abs(review['time_s']-t) < 1e-6 and
                review.get('source_kind') == kind and
                review.get('review_provenance') ==
                    ('synthetic_cpu' if synthetic else 'human_frame_review') and
                review.get('forward_video_sha256') ==
                    media_hashes.get('forward.mkv', 'synthetic_cpu') and
                review.get('overview_video_sha256') ==
                    media_hashes.get('overview.mkv', 'synthetic_cpu') and
                type(review.get('device_face_pixel_reviewed')) is bool and
                (type(review.get('device_face_visible')) is bool
                 if review['device_face_pixel_reviewed'] else
                 review.get('device_face_visible') is None) and
                type(review.get('approach_area_pixel_reviewed')) is bool and
                (type(review.get('approach_area_visible')) is bool
                 if review['approach_area_pixel_reviewed'] else
                 review.get('approach_area_visible') is None),
                f'video/review join {i}')
        observed.append({'frame': i, 'native_frame': native, 'time_s': t,
                         'source_kind': kind, 'ego': row['ego'],
                         'observed_lane_id': -1})
        camera.append({'frame': i, 'native_frame': native,
                       'video_frame': i, 'time_s': t, 'source_kind': kind})
    output.mkdir(parents=True)
    for name, data in zip(SAVED, (observed, camera, reviews)):
        (output / name).write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                           for row in data))
    receipt = {'format': 'c10389-device-raw-to-saved-v1',
               'case_id': cfg['case_id'], 'candidate_id': cfg['candidate_id'],
               'source_kind': kind, 'config_sha256': sha(bundle / 'config.json'),
               'raw_hashes': hashes, 'media_hashes': media_hashes,
               'saved_hashes': {name: sha(output / name) for name in SAVED},
               'original_native_observed': not synthetic,
               'official_placement_verified': False,
               'police_direction_verified': False,
               'legal_verdict': None, 'delivery_ready': False}
    (output / 'preparation-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def measure(bundle, saved):
    bundle, saved = map(Path, (bundle, saved))
    check(bundle)
    cfg = read(bundle / 'config.json')
    receipt = read(saved / 'preparation-receipt.json')
    observations, cameras, reviews = (rows(saved / name) for name in SAVED)
    require(receipt.get('config_sha256') == sha(bundle / 'config.json') and
            receipt.get('source_kind') in ('synthetic_cpu', 'original_native') and
            receipt.get('original_native_observed') ==
                (receipt['source_kind'] == 'original_native') and
            receipt.get('official_placement_verified') is False and
            receipt.get('police_direction_verified') is False and
            receipt.get('legal_verdict') is None and
            receipt.get('delivery_ready') is False and
            all(receipt['saved_hashes'][name] == sha(saved / name) for name in SAVED) and
            len(observations) == len(cameras) == len(reviews) == 240,
            'prepared source and joins')
    stopped_before = crossed = face_reviewed = line_reviewed = 0
    first_crossing = None
    for i, (row, camera, review) in enumerate(zip(observations, cameras, reviews)):
        require(row['frame'] == camera['frame'] == review['frame'] == i and
                row['native_frame'] == camera['native_frame'] == review['native_frame'] and
                row['source_kind'] == camera['source_kind'] ==
                    review['source_kind'] == receipt['source_kind'], f'prepared frame {i}')
        body = row['ego']['body_native_xyz_m']
        front = max(point[0] for point in body)
        rear = min(point[0] for point in body)
        if front < cfg['device_s_m'] and row['ego']['speed_mps'] <= .1:
            stopped_before += 1
        if front >= cfg['device_s_m'] and rear <= cfg['device_s_m']:
            crossed += 1
            if first_crossing is None:
                first_crossing = i
        face_reviewed += int(review['device_face_pixel_reviewed'] and
                             review['device_face_visible'] is True)
        line_reviewed += int(review['approach_area_pixel_reviewed'] and
                             review['approach_area_visible'] is True)
    return {'format': 'c10389-device-prepared-measurement-v1',
            'case_id': cfg['case_id'], 'candidate_id': cfg['candidate_id'],
            'source_kind': receipt['source_kind'],
            'requested_obey': cfg['requested_obey'],
            'stopped_before_device_frames': stopped_before,
            'front_body_at_device_station_frames': crossed,
            'first_body_at_device_station_frame': first_crossing,
            'reviewed_visible_device_face_frames': face_reviewed,
            'reviewed_visible_approach_area_frames': line_reviewed,
            'authored_signal_is_official_placement': False,
            'police_direction_verified': False,
            'signal_specific_exception_reviewed': False,
            'original_native_observed': receipt['original_native_observed'],
            'legal_verdict': None, 'delivery_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--raw-folder', type=Path)
    parser.add_argument('--saved-folder', type=Path, required=True)
    parser.add_argument('--synthetic-cpu', action='store_true')
    args = parser.parse_args()
    result = (prepare(args.bundle, args.raw_folder, args.saved_folder, args.synthetic_cpu)
              if args.raw_folder else measure(args.bundle, args.saved_folder))
    print(json.dumps(result))
