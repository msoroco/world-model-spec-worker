"""Source-bound paragraph (c)(1) raw preparation and conservative distance measurement."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from check import check

RAW = ('native-map-readback.json', 'native-raw-actors.jsonl',
       'video_frames.jsonl', 'frame-review.jsonl', 'native-capture-report.json')
BOUNDARY_M = 60.96


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


def vehicle(value, actor_id):
    require(type(value) is dict and value.get('actor_id') == actor_id and
            value.get('blueprint') == 'vehicle.tesla.model3', 'actor identity')
    center = value.get('center_native_xyz_m')
    velocity = value.get('velocity_native_xyz_mps')
    body = value.get('body_native_xyz_m')
    require(type(center) is list and len(center) == 3 and all(map(finite, center)) and
            type(velocity) is list and len(velocity) == 3 and all(map(finite, velocity)) and
            finite(value.get('yaw_deg')) and finite(value.get('speed_mps')) and
            value['speed_mps'] >= 0 and
            abs(math.sqrt(sum(v*v for v in velocity))-value['speed_mps']) < .01 and
            type(body) is list and len(body) == 8 and
            all(type(p) is list and len(p) == 3 and all(map(finite, p)) for p in body),
            'actor pose/body/speed')
    xs = [p[0] for p in body]
    ys = [p[1] for p in body]
    require(3 <= max(xs)-min(xs) <= 7 and 1.3 <= max(ys)-min(ys) <= 7 and
            abs((max(xs)+min(xs))/2-center[0]) < 1 and
            abs((max(ys)+min(ys))/2-center[1]) < 1 and
            len({(round(p[0], 4), round(p[1], 4)) for p in body}) == 4,
            'actor body geometry')
    return value


def media_hashes(raw, synthetic):
    if synthetic:
        return {}
    result = {}
    for name in ('forward.mkv', 'overview.mkv'):
        result[name] = sha(raw/name)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                '-select_streams', 'v:0',
                                '-show_entries', 'stream=codec_name,nb_read_frames',
                                '-of', 'json', str(raw/name)], capture_output=True,
                               text=True, check=True, timeout=120)
        streams = json.loads(probe.stdout).get('streams', [])
        require(len(streams) == 1 and streams[0].get('codec_name') == 'ffv1' and
                streams[0].get('nb_read_frames') == '240', 'original FFV1 frames')
    return result


def prepare(bundle, raw, output, synthetic=False):
    bundle, raw, output = map(Path, (bundle, raw, output))
    checked = check(bundle)
    cfg = read(bundle/'config.json')
    require(not output.exists(), 'saved output must be fresh')
    hashes = {name: sha(raw/name) for name in RAW}
    mapping = read(raw/RAW[0])
    report = read(raw/RAW[-1])
    observed = rows(raw/RAW[1])
    video = rows(raw/RAW[2])
    reviews = rows(raw/RAW[3])
    requests = rows(bundle/'requested-tracks.jsonl')
    kind = 'synthetic_cpu' if synthetic else 'original_native'
    require(len(observed) == len(video) == len(reviews) == len(requests) == 240,
            '240-frame coverage')
    lane_map = {str(n): {'road_id': 212, 'lane_id': n} for n in (-2, -1)}
    require(mapping.get('source_kind') == kind and
            mapping.get('road_sha256') == sha(bundle/'unmarked-pass.xodr') and
            type(mapping.get('native_map_sha256')) is str and
            len(mapping['native_map_sha256']) == 64 and
            mapping.get('driving_lane_readback') == lane_map and
            mapping.get('authored_shoulder_lane_readback') is True and
            type(mapping.get('ego_actor_id')) is int and
            type(mapping.get('lead_actor_id')) is int and
            mapping['ego_actor_id'] != mapping['lead_actor_id'] and
            mapping.get('pavement_condition_verified') is False and
            mapping.get('legal_verdict') is None, 'map and actor binding')
    require(report.get('case_id') == checked['case_id'] and
            report.get('candidate_id') == checked['candidate_id'] and
            report.get('config_sha256') == sha(bundle/'config.json') and
            report.get('requested_frames') == report.get('observed_frames') == 240 and
            report.get('error') is None and report.get('accepted') is False and
            report.get('delivery_ready') is False and
            report.get('authored_shoulder_lane_readback') is True and
            report.get('pavement_condition_verified') is False and
            report.get('legal_verdict') is None, 'unaccepted capture report')
    media = media_hashes(raw, synthetic)
    first = observed[0].get('native_frame')
    require(type(first) is int, 'first native frame')
    saved, cameras = [], []
    for i, (row, frame, review, request) in enumerate(zip(observed, video, reviews, requests)):
        native, time = first+i, row.get('time_s')
        require(row.get('frame') == i and row.get('native_frame') == native and
                row.get('source_kind') == kind and finite(time) and
                abs(time-(i+1)/20) < .005 and
                row.get('requested_ego_x_m') == request['ego_x_m'] and
                row.get('requested_ego_y_m') == request['ego_y_m'] and
                row.get('requested_lead_x_m') == request['lead_x_m'] and
                row.get('observed_ego_road_id') == 212 and
                row.get('observed_ego_lane_id') in (-1, -2) and
                row.get('observed_lead_road_id') == 212 and
                row.get('observed_lead_lane_id') == -1 and
                row.get('authored_shoulder_lane_readback') is True and
                row.get('pavement_condition_verified') is False and
                row.get('legal_verdict') is None, f'actor/request join {i}')
        require(frame.get('video_frame') == i and frame.get('native_frame') == native and
                finite(frame.get('time_s')) and abs(frame['time_s']-time) < 1e-6 and
                review.get('frame') == i and review.get('native_frame') == native and
                finite(review.get('time_s')) and abs(review['time_s']-time) < 1e-6 and
                review.get('source_kind') == kind and
                review.get('review_provenance') ==
                    ('synthetic_cpu' if synthetic else 'human_frame_review') and
                review.get('forward_video_sha256') == media.get('forward.mkv', 'synthetic_cpu') and
                review.get('overview_video_sha256') == media.get('overview.mkv', 'synthetic_cpu') and
                type(review.get('boundary_pixel_reviewed')) is bool and
                type(review.get('pavement_pixel_reviewed')) is bool and
                (type(review.get('unmarked_pavement_visible')) is bool
                 if review['pavement_pixel_reviewed'] else
                 review.get('unmarked_pavement_visible') is None),
                f'video/review join {i}')
        ego = vehicle(row.get('ego'), mapping['ego_actor_id'])
        lead = vehicle(row.get('lead'), mapping['lead_actor_id'])
        saved.append({'frame': i, 'native_frame': native, 'time_s': time,
                      'source_kind': kind, 'ego': ego, 'lead': lead,
                      'observed_ego_lane_id': row['observed_ego_lane_id'],
                      'observed_lead_lane_id': row['observed_lead_lane_id']})
        cameras.append({'frame': i, 'native_frame': native,
                        'video_frame': i, 'time_s': time, 'source_kind': kind})
    output.mkdir(parents=True)
    for name, data in (('native-observed.jsonl', saved),
                       ('camera-frames.jsonl', cameras),
                       ('frame-review.jsonl', reviews)):
        (output/name).write_text(''.join(json.dumps(row, allow_nan=False)+'\n'
                                         for row in data))
    receipt = {'format': 'c146314-paragraph-c1-raw-to-saved-v1',
               'case_id': cfg['case_id'], 'candidate_id': cfg['candidate_id'],
               'source_kind': kind, 'config_sha256': sha(bundle/'config.json'),
               'raw_hashes': hashes, 'media_hashes': media,
               'saved_hashes': {name: sha(output/name) for name in
                                ('native-observed.jsonl', 'camera-frames.jsonl',
                                 'frame-review.jsonl')},
               'original_native_observed': not synthetic,
               'human_boundary_reviewed': all(r['boundary_pixel_reviewed'] for r in reviews),
               'pavement_condition_verified': False, 'legal_verdict': None,
               'delivery_ready': False}
    (output/'preparation-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def measure(bundle, saved_dir):
    bundle, saved_dir = map(Path, (bundle, saved_dir))
    check(bundle)
    receipt = read(saved_dir/'preparation-receipt.json')
    cfg = read(bundle/'config.json')
    observations = rows(saved_dir/'native-observed.jsonl')
    cameras = rows(saved_dir/'camera-frames.jsonl')
    reviews = rows(saved_dir/'frame-review.jsonl')
    require(receipt.get('config_sha256') == sha(bundle/'config.json') and
            receipt.get('source_kind') in ('synthetic_cpu', 'original_native') and
            receipt.get('original_native_observed') ==
                (receipt.get('source_kind') == 'original_native') and
            receipt.get('pavement_condition_verified') is False and
            receipt.get('legal_verdict') is None and
            receipt.get('delivery_ready') is False and
            all(receipt['saved_hashes'][name] == sha(saved_dir/name) for name in
                ('native-observed.jsonl', 'camera-frames.jsonl', 'frame-review.jsonl')) and
            len(observations) == len(cameras) == len(reviews) == 240,
            'prepared source hashes and rows')
    full, pass_frames, reviewed = [], 0, 0
    for i, (row, cam, review) in enumerate(zip(observations, cameras, reviews)):
        require(row['frame'] == cam['frame'] == review['frame'] == i and
                row['native_frame'] == cam['native_frame'] == review['native_frame'] and
                row['source_kind'] == cam['source_kind'] == review['source_kind'] ==
                    receipt['source_kind'], f'prepared frame join {i}')
        ego, lead = row['ego']['body_native_xyz_m'], row['lead']['body_native_xyz_m']
        ex = [p[0] for p in ego]
        ey = [p[1] for p in ego]
        lx = [p[0] for p in lead]
        ly = [p[1] for p in lead]
        full.append(row['observed_ego_lane_id'] == -2 and
                    min(ey) >= -7 and max(ey) <= -3.5)
        pass_frames += int(min(ex) > max(lx) and max(ey) < min(ly))
        reviewed += int(review['boundary_pixel_reviewed'] and
                        review['pavement_pixel_reviewed'])
    spans = []
    start = None
    for i, occupied in enumerate(full + [False]):
        if occupied and start is None:
            start = i
        if not occupied and start is not None:
            end = i-1
            centers = [observations[j]['ego']['center_native_xyz_m'] for j in range(start, end+1)]
            lower = sum(math.dist(a[:2], b[:2]) for a, b in zip(centers, centers[1:]))
            before = observations[max(0, start-1)]['ego']['center_native_xyz_m']
            after = observations[min(239, end+1)]['ego']['center_native_xyz_m']
            uncertainty = math.dist(before[:2], centers[0][:2]) + math.dist(centers[-1][:2], after[:2])
            complete_exit = end < 239
            spans.append({'first_frame': start, 'last_frame': end,
                          'exit_observed': complete_exit,
                          'sampled_distance_lower_m': round(lower, 6),
                          'boundary_uncertainty_m': round(uncertainty, 6),
                          'distance_upper_m': round(lower+uncertainty, 6) if complete_exit else None,
                          'boundary_relation': ('incomplete_exit' if not complete_exit else
                              'within_200ft' if lower+uncertainty <= BOUNDARY_M
                              else 'over_200ft' if lower > BOUNDARY_M else 'ambiguous')})
            start = None
    return {'format': 'c146314-paragraph-c1-prepared-measurement-v1',
            'case_id': cfg['case_id'], 'candidate_id': cfg['candidate_id'],
            'source_kind': receipt['source_kind'],
            'requested_excursion_m': cfg['requested_excursion_m'],
            'requested_distance_is_observed_distance': False,
            'full_body_unmarked_frames': sum(full), 'spans': spans,
            'right_pass_frames': pass_frames, 'reviewed_boundary_pavement_frames': reviewed,
            'original_native_observed': receipt['original_native_observed'],
            'pavement_condition_verified': False, 'legal_verdict': None,
            'delivery_ready': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--raw-folder', type=Path)
    p.add_argument('--saved-folder', type=Path, required=True)
    p.add_argument('--synthetic-cpu', action='store_true')
    a = p.parse_args()
    if a.raw_folder:
        print(json.dumps(prepare(a.bundle, a.raw_folder, a.saved_folder, a.synthetic_cpu)))
    else:
        print(json.dumps(measure(a.bundle, a.saved_folder)))
