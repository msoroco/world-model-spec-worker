"""Synthetic raw-to-saved pass preparation with altered-source controls."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from prepare_pass import prepare

HERE = Path(__file__).resolve().parent
NAMES = ('native-raw-actors.jsonl', 'native-map-readback.json',
         'video_frames.jsonl', 'forward-video-stub.txt')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2)+'\n')


def write_rows(path, data):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in data))


def actor(actor_id, blueprint, x, y, speed, direction):
    native_y = -y
    velocity = direction*speed
    body = [[x+dx, native_y+dy, 0] for dx in (-2.2, 2.2) for dy in (-.9, .9)]
    return {'actor_id': actor_id, 'blueprint': blueprint,
            'center_native_xyz_m': [x, native_y, 0], 'yaw_deg': 0 if direction>0 else 180,
            'velocity_native_xyz_mps': [velocity, 0, 0], 'speed_mps': speed,
            'body_native_xyz_m': body}


def fixture(distance):
    raw_folder = HERE/'raw-fixtures'/str(distance)
    raw_folder.mkdir(parents=True, exist_ok=True)
    config = HERE/'drafts'/str(distance)/'primary'/'config.json'
    plan = json.loads(config.read_text())
    saved_folder = HERE/'saved-fixtures'/str(distance)
    source = [json.loads(line) for line in (saved_folder/'native-observed.jsonl').read_text().splitlines()]
    raw, frames, review_rows = [], [], []
    for row in source:
        i = row['frame']
        raw.append({'frame': i, 'native_frame': row['native_frame'],
                    'time_s': row['time_s'], 'source_kind': 'synthetic_cpu',
                    'ego': actor(1, 'vehicle.tesla.model3', row['ego_x_m'], row['ego_y_m'],
                                 row['ego_speed_mps'], 1),
                    'overtaken': actor(2, 'vehicle.audi.tt', row['overtaken_x_m'],
                                       row['overtaken_y_m'], row['overtaken_speed_mps'], 1),
                    'oncoming': actor(3, 'vehicle.audi.tt', row['oncoming_x_m'],
                                      row['oncoming_y_m'], row['oncoming_speed_mps'], -1)})
        frames.append({'video_frame': i, 'native_frame': row['native_frame'],
                       'time_s': row['time_s']})
        review_rows.append({'frame': i, 'native_frame': row['native_frame'],
                            'time_s': row['time_s'],
                            'sightline_visible': row['sightline_visible'],
                            'driver_eye_clear_m': row['driver_eye_clear_m']})
    write_rows(raw_folder/'native-raw-actors.jsonl', raw)
    write_rows(raw_folder/'video_frames.jsonl', frames)
    write_json(raw_folder/'native-map-readback.json', {
        'road_sha256': plan['road_sha256'], 'native_map_sha256': 'a'*64,
        'right_lane_id': -1, 'opposing_lane_id': 1,
        'ego_actor_id': 1, 'overtaken_actor_id': 2, 'oncoming_actor_id': 3,
        'highway_status_reviewed': False})
    (raw_folder/'forward-video-stub.txt').write_text('C102951 synthetic camera stub '+str(distance)+'\n')
    source_hashes = {name: sha(raw_folder/name) for name in NAMES[:-1]}
    source_hashes['forward_video'] = sha(raw_folder/NAMES[-1])
    review_path = raw_folder/'sightline-review.json'
    write_json(review_path, {'format': 'c102951-sightline-review-v1',
                             'source_kind': 'synthetic_cpu',
                             'review_provenance': 'synthetic_cpu',
                             'source_hashes': source_hashes, 'rows': review_rows})
    return raw_folder, review_path, config


def rejected(raw, review, config, mutate, refresh_hashes=False):
    with tempfile.TemporaryDirectory(dir=HERE) as temporary:
        root = Path(temporary)
        copy = root/'raw'
        shutil.copytree(raw, copy)
        review_copy = copy/'sightline-review.json'
        mutate(copy, review_copy)
        if refresh_hashes:
            packet = json.loads(review_copy.read_text())
            packet['source_hashes'] = {name: sha(copy/name) for name in NAMES[:-1]}
            packet['source_hashes']['forward_video'] = sha(copy/NAMES[-1])
            write_json(review_copy, packet)
        try:
            prepare(copy, review_copy, root/'prepared', config)
        except (ValueError, TypeError):
            return True
        raise AssertionError('Changed raw pass/review accepted')


def prove():
    positives, negatives = [], []
    for distance in (70, 120, 170):
        raw, review, config = fixture(distance)
        output = HERE/'prepared-fixtures'/str(distance)
        if output.exists():
            shutil.rmtree(output)
        receipt = prepare(raw, review, output, config)
        if (receipt['measurement']['entry_oncoming_body_gap_m'] != distance or
                receipt['measurement']['legal_verdict'] is not None or
                receipt['delivery_ready']):
            raise AssertionError('Prepared synthetic pass differs')
        positives.append({'distance_m': distance, 'source_hashes': receipt['source_hashes'],
                          'review_sha256': sha(review),
                          'prepared_receipt_sha256': sha(output/'preparation-receipt.json'),
                          'entry_oncoming_body_gap_m': distance})
        mutations = {
            'changed_video_bytes': lambda folder, path:
                (folder/'forward-video-stub.txt').write_text('changed camera bytes\n'),
            'missing_review_frame': lambda folder, path:
                write_json(path, {**json.loads(path.read_text()),
                                  'rows': json.loads(path.read_text())['rows'][:-1]}),
            'wrong_frame_map_join': lambda folder, path:
                write_rows(folder/'video_frames.jsonl', [
                    {**row, 'native_frame': 99} if i == 40 else row
                    for i, row in enumerate(json.loads(line) for line in
                                             (folder/'video_frames.jsonl').read_text().splitlines())]),
            'wrong_actor_id': lambda folder, path:
                write_rows(folder/'native-raw-actors.jsonl', [
                    {**row, 'ego': {**row['ego'], 'actor_id': 99}} if i == 40 else row
                    for i, row in enumerate(json.loads(line) for line in
                                             (folder/'native-raw-actors.jsonl').read_text().splitlines())]),
        }
        for name, mutate in mutations.items():
            negatives.append({'distance_m': distance, 'mutation': name,
                              'rejected': rejected(raw, review, config, mutate,
                                                   refresh_hashes=name in
                                                   ('wrong_frame_map_join', 'wrong_actor_id'))})
    proof = {'format': 'c102951-raw-to-saved-preparation-proof-v1',
             'assignment_id': HERE.parent.name,
             'preparer_sha256': sha(HERE/'prepare_pass.py'),
             'pass_processor_sha256': sha(HERE/'measure_pass.py'),
             'positives': positives, 'negatives': negatives,
             'original_native_observed': False,
             'legal_verdict': None, 'delivery_ready': False}
    write_json(HERE/'preparation-proof.json', proof)
    return proof


if __name__ == '__main__':
    result = prove()
    print(json.dumps({'positives': len(result['positives']),
                      'negatives': len(result['negatives'])}))
