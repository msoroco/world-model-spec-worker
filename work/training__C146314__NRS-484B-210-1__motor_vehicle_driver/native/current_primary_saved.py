"""Saved-only paragraph (d) right-pass geometry from original Native sources.

An authored one-way road is not proof of a legally restricted highway.
The meter reports body relations and preserves the legal decision as unknown.
"""

import hashlib
import json
import math
from pathlib import Path
import subprocess

CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
FRAMES = 600
FIXTURE_MEDIA = b'C146314 SYNTHETIC MARKER; NOT ORIGINAL VIDEO\n'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def require(value, message):
    if not value:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def body(actor, expected_id):
    points = actor.get('body_native_xyz_m')
    center = actor.get('center_native_xyz_m')
    velocity = actor.get('velocity_native_xyz_mps')
    require(actor.get('actor_id') == expected_id and
            isinstance(points, list) and len(points) == 8 and
            all(isinstance(p, list) and len(p) == 3 and all(map(finite, p))
                for p in points) and
            isinstance(center, list) and len(center) == 3 and all(map(finite, center)) and
            isinstance(velocity, list) and len(velocity) == 3 and all(map(finite, velocity)) and
            finite(actor.get('speed_mps')) and
            abs(actor['speed_mps'] - math.sqrt(sum(v*v for v in velocity))) < .03,
            'Original Native actor body or motion invalid')
    require(math.dist(center, [sum(p[k] for p in points)/8 for k in range(3)]) < 1,
            'Original body center differs')
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), max(xs), min(ys), max(ys)


def verify_video(folder, video_rows, synthetic_fixture):
    hashes = {}
    for name, (width, height) in CAMERAS.items():
        path = folder / (name + '.mkv')
        hashes[path.name] = sha(path)
        declared = [row.get('source_rgb_sha256', {}).get(name) for row in video_rows]
        require(all(isinstance(value, str) and len(value) == 64 and
                    all(c in '0123456789abcdef' for c in value)
                    for value in declared), 'Original camera frame hash missing: ' + name)
        if synthetic_fixture:
            require(path.read_bytes() == FIXTURE_MEDIA and
                    all(value == hashlib.sha256(FIXTURE_MEDIA).hexdigest()
                        for value in declared),
                    'Synthetic marker camera hash differs: ' + name)
            continue
        probe = subprocess.run([
            'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name,nb_read_frames,width,height',
            '-of', 'json', str(path)], capture_output=True, text=True, timeout=120)
        require(probe.returncode == 0, 'Original FFV1 probe failed: ' + name)
        streams = json.loads(probe.stdout).get('streams', [])
        require(len(streams) == 1 and streams[0].get('codec_name') == 'ffv1' and
                streams[0].get('nb_read_frames') == str(FRAMES) and
                (streams[0].get('width'), streams[0].get('height')) == (width, height),
                'Original FFV1 video contract differs: ' + name)
        decoder = subprocess.Popen([
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-i', str(path), '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            frame_bytes = width * height * 3
            for index, expected in enumerate(declared):
                raw = decoder.stdout.read(frame_bytes)
                require(len(raw) == frame_bytes and
                        hashlib.sha256(raw).hexdigest() == expected,
                        f'Original decoded frame hash differs: {name} {index}')
            require(not decoder.stdout.read(1), 'Extra original camera frame: ' + name)
            require(decoder.wait(timeout=180) == 0,
                    'Original FFV1 decode failed: ' + name)
        finally:
            if decoder.poll() is None:
                decoder.kill()
                decoder.wait()
            decoder.stdout.close()
            decoder.stderr.close()
    return hashes


def measure(bundle, attempt, review_path, *, synthetic_fixture=False):
    bundle, attempt, review_path = Path(bundle), Path(attempt), Path(review_path)
    config = read(bundle / 'config.json')
    road = bundle / 'one-way-pass.xodr'
    require(config['case_id'].endswith('__witness_1') and
            config['road_sha256'] == sha(road) and config['frames'] == FRAMES,
            'Exact current paragraph (d) construction differs')
    native_path, video_path = attempt / 'native-raw-actors.jsonl', attempt / 'video_frames.jsonl'
    map_path, report_path = attempt / 'native-map-readback.json', attempt / 'native-capture-report.json'
    native, video = rows(native_path), rows(video_path)
    map_receipt, report, review = read(map_path), read(report_path), read(review_path)
    require(len(native) == len(video) == FRAMES, '600 original joined frames required')
    kind = 'synthetic_fixture' if synthetic_fixture else 'original_native'
    require(map_receipt.get('source_kind') == kind and
            map_receipt.get('road_sha256') == sha(road) and
            map_receipt.get('driving_lane_readback') == {
                '-1': {'road_id': 210, 'lane_id': -1},
                '-2': {'road_id': 210, 'lane_id': -2}} and
            type(map_receipt.get('ego_actor_id')) is int and
            type(map_receipt.get('lead_actor_id')) is int and
            map_receipt['ego_actor_id'] != map_receipt['lead_actor_id'] and
            map_receipt.get('one_way_designation_verified') is False and
            map_receipt.get('pavement_condition_verified') is False and
            map_receipt.get('legal_verdict') is None,
            'Native map and unresolved legal context differ')
    require(report.get('case_id') == config['case_id'] and
            report.get('candidate_id') == 'primary' and
            report.get('config_sha256') == sha(bundle / 'config.json') and
            report.get('observed_frames') == FRAMES and
            report.get('error') is None and
            report.get('restoration', {}).get('restored') is True and
            report.get('accepted') is False and
            report.get('delivery_ready') is False and
            report.get('legal_verdict') is None,
            'Native capture/restoration receipt differs')
    media_hashes = verify_video(attempt, video, synthetic_fixture)
    require(review.get('format') == 'c146314-current-primary-source-review-v1' and
            review.get('source_kind') == kind + '_review' and
            isinstance(review.get('reviewer_id'), str) and review['reviewer_id'] and
            review.get('case_id') == config['case_id'] and
            review.get('raw_sha256') == sha(native_path) and
            review.get('video_frames_sha256') == sha(video_path) and
            review.get('map_sha256') == sha(map_path) and
            review.get('capture_report_sha256') == sha(report_path) and
            review.get('media_sha256') == media_hashes and
            all(type(review.get(key)) is bool for key in (
                'one_way_designation_reviewed', 'unobstructed_pavement_reviewed',
                'right_pass_pixels_reviewed')),
            'Original source review binding differs')
    origin = native[0].get('native_frame')
    require(type(origin) is int, 'Native frame origin missing')
    right = ahead = 0
    earlier = None
    for index, (actor_row, image_row) in enumerate(zip(native, video)):
        require(actor_row.get('frame') == image_row.get('video_frame') == index and
                actor_row.get('native_frame') == image_row.get('native_frame') == origin + index and
                image_row.get('carla_frame') == origin + index and
                actor_row.get('source_kind') == kind and
                finite(actor_row.get('time_s')) and finite(image_row.get('time_s')) and
                abs(actor_row['time_s'] - (index + 1)/20) < .005 and
                abs(actor_row['time_s'] - image_row['time_s']) < 1e-6,
                'Original actor/video frame join differs')
        ego = body(actor_row.get('ego', {}), map_receipt['ego_actor_id'])
        lead = body(actor_row.get('lead', {}), map_receipt['lead_actor_id'])
        require(actor_row.get('observed_ego_road_id') == 210 and
                actor_row.get('observed_lead_road_id') == 210 and
                actor_row.get('observed_ego_lane_id') in (-1, -2) and
                actor_row.get('observed_lead_lane_id') == -1 and
                actor_row.get('legal_verdict') is None,
                'Original right-pass road/lane context differs')
        if earlier is not None:
            require(abs(actor_row['ego']['center_native_xyz_m'][0] - earlier) < 3,
                    'Original ego motion discontinuity')
        earlier = actor_row['ego']['center_native_xyz_m'][0]
        is_right = ego[3] < lead[2] and actor_row['observed_ego_lane_id'] == -2
        right += int(is_right)
        ahead += int(is_right and ego[0] > lead[1])
    return {'format': 'c146314-current-primary-saved-measurement-v1',
            'case_id': config['case_id'], 'frames_joined': FRAMES,
            'ego_body_right_of_lead_frames': right,
            'ego_body_ahead_and_right_of_lead_frames': ahead,
            'source_kind': kind, 'raw_sha256': sha(native_path),
            'review_sha256': sha(review_path), 'media_sha256': media_hashes,
            'original_native_observed': not synthetic_fixture,
            'one_way_designation_reviewed': review['one_way_designation_reviewed'],
            'unobstructed_pavement_reviewed': review['unobstructed_pavement_reviewed'],
            'right_pass_pixels_reviewed': review['right_pass_pixels_reviewed'],
            'accepted': False, 'delivery_ready': False, 'legal_verdict': None}
