"""CPU source-shape proof for current 600-frame paragraph (d) saved meter."""

import hashlib
import json
import os
from pathlib import Path
import tempfile

from current_primary_saved import CAMERAS, FIXTURE_MEDIA, measure, sha

HERE = Path(__file__).resolve().parent
BUNDLE = HERE / 'current-primary'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def lines(path, value):
    path.write_text(''.join(json.dumps(row) + '\n' for row in value))


def vehicle(actor_id, x, y, speed):
    center = [x, y, 1.5]
    return {'actor_id': actor_id, 'blueprint': 'vehicle.tesla.model3',
            'center_native_xyz_m': center, 'yaw_deg': 0,
            'velocity_native_xyz_mps': [speed, 0, 0], 'speed_mps': speed,
            'body_native_xyz_m': [[x + dx, y + dy, 1.5 + dz]
                for dx in (-2, 2) for dy in (-.9, .9) for dz in (-.7, .7)]}


def fixture(root):
    cfg = json.loads((BUNDLE / 'config.json').read_text())
    req = [json.loads(row) for row in (BUNDLE / 'requested-tracks.jsonl').read_text().splitlines()]
    map_path = root / 'native-map-readback.json'
    report_path = root / 'native-capture-report.json'
    write(map_path, {'source_kind': 'synthetic_fixture',
        'road_sha256': sha(BUNDLE / 'one-way-pass.xodr'),
        'native_map_sha256': 'a' * 64,
        'driving_lane_readback': {'-1': {'road_id': 210, 'lane_id': -1},
                                  '-2': {'road_id': 210, 'lane_id': -2}},
        'ego_actor_id': 314, 'lead_actor_id': 210,
        'one_way_designation_verified': False,
        'pavement_condition_verified': False, 'legal_verdict': None})
    write(report_path, {'case_id': cfg['case_id'], 'candidate_id': 'primary',
        'config_sha256': sha(BUNDLE / 'config.json'), 'requested_frames': 600,
        'observed_frames': 600, 'restoration': {'restored': True},
        'error': None, 'accepted': False, 'delivery_ready': False,
        'legal_verdict': None})
    raw, video = [], []
    digest = hashlib.sha256(FIXTURE_MEDIA).hexdigest()
    for i, row in enumerate(req):
        t = (i + 1)/20
        ego, lead = vehicle(314, row['ego_x_m'], row['ego_y_m'], 8), \
                    vehicle(210, row['lead_x_m'], -1.75, 4)
        raw.append({'frame': i, 'native_frame': 2000 + i, 'time_s': t,
            'source_kind': 'synthetic_fixture',
            'observed_ego_road_id': 210, 'observed_ego_lane_id': row['ego_lane_id'],
            'observed_lead_road_id': 210, 'observed_lead_lane_id': -1,
            'ego': ego, 'lead': lead, 'legal_verdict': None})
        video.append({'video_frame': i, 'native_frame': 2000 + i,
            'carla_frame': 2000 + i, 'time_s': t,
            'source_rgb_sha256': {name: digest for name in CAMERAS}})
    raw_path, video_path = root / 'native-raw-actors.jsonl', root / 'video_frames.jsonl'
    lines(raw_path, raw)
    lines(video_path, video)
    media = {}
    for name in CAMERAS:
        path = root / (name + '.mkv')
        path.write_bytes(FIXTURE_MEDIA)
        media[path.name] = sha(path)
    review_path = root / 'source-review.json'
    write(review_path, {'format': 'c146314-current-primary-source-review-v1',
        'source_kind': 'synthetic_fixture_review', 'reviewer_id': 'cpu-fixture-only',
        'case_id': cfg['case_id'], 'raw_sha256': sha(raw_path),
        'video_frames_sha256': sha(video_path), 'map_sha256': sha(map_path),
        'capture_report_sha256': sha(report_path), 'media_sha256': media,
        'one_way_designation_reviewed': False,
        'unobstructed_pavement_reviewed': False,
        'right_pass_pixels_reviewed': False})
    return review_path


def main():
    if not os.environ.get('TMPDIR', '').endswith('c146314-210-1'):
        raise ValueError('Task-specific scratch directory required')
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as name:
        root = Path(name)
        review = fixture(root)
        positive = measure(BUNDLE, root, review, synthetic_fixture=True)
        if positive['ego_body_right_of_lead_frames'] <= 0 or \
                positive['ego_body_ahead_and_right_of_lead_frames'] <= 0 or \
                positive['original_native_observed'] or positive['legal_verdict'] is not None:
            raise AssertionError('Synthetic right-pass meter overclaimed or missed geometry')
        negative = []
        raw_path, video_path = root / 'native-raw-actors.jsonl', root / 'video_frames.jsonl'
        def reject(label, path, edit, *, refresh=False):
            original = path.read_bytes()
            old_review = review.read_bytes()
            try:
                data = [json.loads(line) for line in path.read_text().splitlines()]
                edit(data)
                lines(path, data)
                if refresh:
                    r = json.loads(review.read_text())
                    r['raw_sha256'] = sha(raw_path)
                    r['video_frames_sha256'] = sha(video_path)
                    write(review, r)
                try:
                    measure(BUNDLE, root, review, synthetic_fixture=True)
                except ValueError as exc:
                    negative.append({'name': label, 'error': str(exc)})
                else:
                    raise AssertionError('Changed source accepted: ' + label)
            finally:
                path.write_bytes(original)
                review.write_bytes(old_review)
        reject('camera_frame_digest', video_path,
               lambda rows: rows[100]['source_rgb_sha256'].update(overview='0'*64), refresh=True)
        reject('ego_identity', raw_path,
               lambda rows: rows[200]['ego'].update(actor_id=315), refresh=True)
        reject('native_frame_join', video_path,
               lambda rows: rows[300].update(native_frame=5000), refresh=True)
        reject('body_geometry', raw_path,
               lambda rows: rows[400]['ego']['body_native_xyz_m'][0].__setitem__(0, 1000),
               refresh=True)
        reject('lane_readback', raw_path,
               lambda rows: rows[500].update(observed_ego_road_id=211), refresh=True)
        try:
            measure(BUNDLE, root, review)
        except ValueError:
            negative.append({'name': 'marker_rejected_as_original',
                             'error': 'Synthetic marker media is not original FFV1'})
        else:
            raise AssertionError('Synthetic marker accepted as original video')
    return {'format': 'c146314-current-primary-saved-cpu-proof-v1',
            'case_id': positive['case_id'], 'positive_count': 1,
            'negative_rejections': negative,
            'positive_measurement': positive,
            'original_native_observed': False, 'legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
