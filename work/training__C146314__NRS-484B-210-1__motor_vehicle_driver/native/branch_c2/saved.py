"""Source-bound paragraph (c)(2) private-way raw preparation and crossing measurement."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from check import check

RAW = ('native-map-readback.json', 'native-raw-actors.jsonl',
       'video_frames.jsonl', 'frame-review.jsonl', 'native-capture-report.json')


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
            mapping.get('private_way_verified') is cfg['private_way_requested'] and
            (mapping.get('private_way_road_readback') == {'road_id': 214, 'lane_id': -1}
             if cfg['private_way_requested'] else
             mapping.get('private_way_road_readback') is None or
             mapping['private_way_road_readback'].get('road_id') != 214) and
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
            report.get('private_way_verified') is cfg['private_way_requested'] and
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
                row.get('private_way_verified') is cfg['private_way_requested'] and
                row.get('private_way_road_readback') == mapping['private_way_road_readback'] and
                row.get('actual_private_way_passed_observed') is False and
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
                type(review.get('private_way_pixel_reviewed')) is bool and
                (type(review.get('private_way_visible')) is bool
                 if review['private_way_pixel_reviewed'] else
                 review.get('private_way_visible') is None) and
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
                      'observed_lead_lane_id': row['observed_lead_lane_id'],
                      'private_way_verified': row['private_way_verified'],
                      'private_way_road_readback': row['private_way_road_readback']})
        cameras.append({'frame': i, 'native_frame': native,
                        'video_frame': i, 'time_s': time, 'source_kind': kind})
    output.mkdir(parents=True)
    for name, data in (('native-observed.jsonl', saved),
                       ('camera-frames.jsonl', cameras),
                       ('frame-review.jsonl', reviews)):
        (output/name).write_text(''.join(json.dumps(row, allow_nan=False)+'\n'
                                         for row in data))
    receipt = {'format': 'c146314-paragraph-c2-raw-to-saved-v1',
               'case_id': cfg['case_id'], 'candidate_id': cfg['candidate_id'],
               'source_kind': kind, 'config_sha256': sha(bundle/'config.json'),
               'raw_hashes': hashes, 'media_hashes': media,
               'saved_hashes': {name: sha(output/name) for name in
                                ('native-observed.jsonl', 'camera-frames.jsonl',
                                 'frame-review.jsonl')},
               'original_native_observed': not synthetic,
               'human_private_way_reviewed': all(r['private_way_pixel_reviewed'] for r in reviews),
               'private_way_verified': mapping['private_way_verified'],
               'pavement_condition_verified': False, 'legal_verdict': None,
               'delivery_ready': False}
    (output/'preparation-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def measure(bundle, saved_dir):
    bundle, saved_dir = map(Path, (bundle, saved_dir))
    check(bundle)
    receipt = read(saved_dir/'preparation-receipt.json')
    cfg = read(bundle/'config.json')
    names = ('native-observed.jsonl', 'camera-frames.jsonl', 'frame-review.jsonl')
    require(receipt.get('config_sha256') == sha(bundle/'config.json') and
            receipt.get('source_kind') in ('synthetic_cpu', 'original_native') and
            receipt.get('original_native_observed') ==
                (receipt.get('source_kind') == 'original_native') and
            receipt.get('private_way_verified') is cfg['private_way_requested'] and
            receipt.get('delivery_ready') is False and
            all(receipt['saved_hashes'][name] == sha(saved_dir/name) for name in names),
            'prepared source hashes')
    observations, cameras, reviews = (rows(saved_dir/name) for name in names)
    require(len(observations) == len(cameras) == len(reviews) == 240,
            'prepared frame count')
    full, pass_frames, reviewed, crossing_frames = [], 0, 0, []
    plane = cfg['private_way_x_m']
    for i, (row, cam, review) in enumerate(zip(observations, cameras, reviews)):
        require(row['frame'] == cam['frame'] == review['frame'] == i and
                row['native_frame'] == cam['native_frame'] == review['native_frame'] and
                row['source_kind'] == cam['source_kind'] == review['source_kind'] ==
                    receipt['source_kind'] and
                row['private_way_verified'] is cfg['private_way_requested'],
                f'prepared frame join {i}')
        ego, lead = row['ego']['body_native_xyz_m'], row['lead']['body_native_xyz_m']
        ex, ey = [p[0] for p in ego], [p[1] for p in ego]
        lx, ly = [p[0] for p in lead], [p[1] for p in lead]
        occupied = (row['observed_ego_lane_id'] == -2 and
                    min(ey) >= -7 and max(ey) <= -3.5)
        full.append(occupied)
        pass_frames += int(min(ex) > max(lx) and max(ey) < min(ly))
        reviewed += int(review['private_way_pixel_reviewed'] and
                        review['pavement_pixel_reviewed'])
        if occupied and min(ex) <= plane <= max(ex):
            crossing_frames.append(i)
    spans = []
    first = None
    for i, occupied in enumerate(full + [False]):
        if occupied and first is None:
            first = i
        if not occupied and first is not None:
            spans.append({'first_frame': first, 'last_frame': i-1,
                          'exit_observed': i-1 < 239})
            first = None
    body_crossed = bool(crossing_frames) and any(
        observations[i-1]['ego']['center_native_xyz_m'][0] < plane <=
        observations[i]['ego']['center_native_xyz_m'][0]
        for i in range(1, 240) if full[i-1] and full[i])
    # The authored road readback alone does not establish a visible private way.
    return {'format': 'c146314-paragraph-c2-prepared-measurement-v1',
            'case_id': cfg['case_id'], 'candidate_id': cfg['candidate_id'],
            'source_kind': receipt['source_kind'],
            'private_way_requested': cfg['private_way_requested'],
            'private_way_road_readback_verified': receipt['private_way_verified'],
            'full_body_unmarked_frames': sum(full), 'spans': spans,
            'body_at_spur_plane_frames': crossing_frames,
            'body_crossed_spur_plane': body_crossed,
            'right_pass_frames': pass_frames,
            'reviewed_private_way_pavement_frames': reviewed,
            'original_native_observed': receipt['original_native_observed'],
            'physical_private_way_crossing_verified': False,
            'legal_verdict': None, 'delivery_ready': False}


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
