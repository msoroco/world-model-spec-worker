"""Independent raw/review/saved row audit and negative replay for C102951."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from prepare_pass import prepare

HERE = Path(__file__).resolve().parent
NAMES = ('native-raw-actors.jsonl', 'native-map-readback.json',
         'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, data):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in data))


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2)+'\n')


def replay_negative(raw_folder, config, mutation):
    with tempfile.TemporaryDirectory(dir=HERE) as temporary:
        root = Path(temporary)
        copy = root/'raw'
        shutil.copytree(raw_folder, copy)
        review_path = copy/'sightline-review.json'
        review = json.loads(review_path.read_text())
        if mutation == 'changed_video_bytes':
            (copy/'forward-video-stub.txt').write_text('independent camera alteration\n')
        elif mutation == 'missing_review_frame':
            review['rows'] = review['rows'][:-1]
            write_json(review_path, review)
        elif mutation == 'wrong_frame_map_join':
            frames = load_rows(copy/'video_frames.jsonl')
            frames[40]['native_frame'] = 99
            write_rows(copy/'video_frames.jsonl', frames)
        elif mutation == 'wrong_actor_id':
            rows = load_rows(copy/'native-raw-actors.jsonl')
            rows[40]['ego']['actor_id'] = 99
            write_rows(copy/'native-raw-actors.jsonl', rows)
        else:
            raise ValueError('Unknown negative control')
        if mutation in ('wrong_frame_map_join', 'wrong_actor_id'):
            review['source_hashes'] = {name: sha(copy/name) for name in NAMES}
            review['source_hashes']['forward_video'] = sha(copy/'forward-video-stub.txt')
            write_json(review_path, review)
        try:
            prepare(copy, review_path, root/'prepared', config)
        except (ValueError, TypeError):
            return
        raise AssertionError('Independent changed raw packet accepted')


def audit():
    proof_path = HERE/'preparation-proof.json'
    proof = json.loads(proof_path.read_text())
    if (proof['format'] != 'c102951-raw-to-saved-preparation-proof-v1' or
            proof['assignment_id'] != HERE.parent.name or
            proof['preparer_sha256'] != sha(HERE/'prepare_pass.py') or
            proof['pass_processor_sha256'] != sha(HERE/'measure_pass.py') or
            proof['original_native_observed'] or proof['delivery_ready'] or
            proof['legal_verdict'] is not None or
            {p['distance_m'] for p in proof['positives']} != {70, 120, 170} or
            len(proof['negatives']) != 12):
        raise ValueError('Preparation proof provenance or coverage differs')
    count, rejections = 0, 0
    for positive in proof['positives']:
        distance = positive['distance_m']
        raw_folder = HERE/'raw-fixtures'/str(distance)
        output = HERE/'prepared-fixtures'/str(distance)
        config = HERE/'drafts'/str(distance)/'primary'/'config.json'
        source_hashes = {name: sha(raw_folder/name) for name in NAMES}
        source_hashes['forward_video'] = sha(raw_folder/'forward-video-stub.txt')
        review_path = raw_folder/'sightline-review.json'
        review = json.loads(review_path.read_text())
        receipt = json.loads((output/'preparation-receipt.json').read_text())
        road = json.loads((output/'road-readback.json').read_text())
        if (positive['source_hashes'] != source_hashes or
                positive['review_sha256'] != sha(review_path) or
                positive['prepared_receipt_sha256'] != sha(output/'preparation-receipt.json') or
                receipt['source_hashes'] != source_hashes or
                receipt['saved_hashes'] != {name: sha(output/name) for name in
                                            ('native-observed.jsonl', 'road-readback.json')} or
                road['source_hashes'] != source_hashes or
                review['source_hashes'] != source_hashes or
                road['sightline_review_sha256'] != sha(review_path)):
            raise ValueError('Raw/review/saved source hash differs')
        raw = load_rows(raw_folder/'native-raw-actors.jsonl')
        frames = load_rows(raw_folder/'video_frames.jsonl')
        saved = load_rows(output/'native-observed.jsonl')
        if not (len(raw) == len(frames) == len(saved) == 480):
            raise ValueError('Prepared frame coverage differs')
        first_entry = None
        for i, (actor_row, frame, row, sight) in enumerate(zip(raw, frames, saved, review['rows'])):
            if (actor_row['frame'] != i or frame['video_frame'] != i or
                    row['frame'] != i or sight['frame'] != i or
                    actor_row['native_frame'] != frame['native_frame'] != row['native_frame'] != sight['native_frame'] or
                    actor_row['time_s'] != frame['time_s'] != row['time_s'] != sight['time_s'] or
                    row['sightline_visible'] is not sight['sightline_visible'] or
                    row['driver_eye_clear_m'] != sight['driver_eye_clear_m']):
                raise ValueError('Raw/video/review/saved frame join differs')
            for name in ('ego', 'overtaken', 'oncoming'):
                center = actor_row[name]['center_native_xyz_m']
                if (row[name+'_x_m'] != center[0] or row[name+'_y_m'] != -center[1] or
                        row[name+'_speed_mps'] != actor_row[name]['speed_mps']):
                    raise ValueError('Prepared actor pose or speed differs')
            if first_entry is None and row['ego_y_m']+.9 > 0:
                first_entry = row
            count += 1
        if first_entry is None or round(first_entry['oncoming_x_m']-first_entry['ego_x_m']-4.4, 3) != distance:
            raise ValueError('Prepared sweep entry gap differs')
        controls = [n for n in proof['negatives'] if n['distance_m'] == distance]
        if {n['mutation'] for n in controls} != {
                'changed_video_bytes', 'missing_review_frame',
                'wrong_frame_map_join', 'wrong_actor_id'} or not all(n['rejected'] is True for n in controls):
            raise ValueError('Preparation negative coverage differs')
        for control in controls:
            replay_negative(raw_folder, config, control['mutation'])
            rejections += 1
    receipt = {'format': 'c102951-independent-preparation-audit-v1',
               'assignment_id': HERE.parent.name,
               'proof_sha256': sha(proof_path),
               'raw_review_saved_rows_recomputed': count,
               'negative_controls_replayed': rejections,
               'original_native_observed': False, 'delivery_ready': False}
    (HERE/'preparation-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit()))
