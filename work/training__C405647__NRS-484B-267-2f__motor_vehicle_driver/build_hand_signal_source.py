"""Build a 600-frame source-shaped diagnostic for the driver hand alternative."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__visible_hand_signal'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = HERE / 'current-fixture/controlled_2'
    target = HERE / 'hand-signal-source'
    target.mkdir(exist_ok=True)
    for name in ('video_frames.jsonl', 'vehicle_poses.jsonl'):
        shutil.copyfile(source / name, target / name)
    frames = [json.loads(line) for line in (target / 'video_frames.jsonl').read_text().splitlines()]
    track = []
    for index, frame in enumerate(frames):
        track.append({'video_frame': index, 'native_frame': frame['native_frame'],
                      'actor_id': 110, 'source_vehicle_actor_id': 108,
                      'signal_active': 80 <= index < 100,
                      'pose_bones_requested': ['crl_shoulder__R', 'crl_arm__R',
                                               'crl_foreArm__R', 'crl_hand__R']
                      if 80 <= index < 100 else [],
                      'source_kind': 'synthetic_native_sample'})
    (target / 'driver_hand_track.jsonl').write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in track))
    review = {'case_id': CASE, 'review_kind': 'synthetic_diagnostic',
              'reviewer': 'synthetic diagnostic fixture', 'ego_actor_id': 107,
              'source_vehicle_actor_id': 108, 'source_driver_actor_id': 110,
              'preparing_to_move': True,
              'driver_identity_source': 'synthetic-fixture:identity',
              'hand_signal_visual_source': 'synthetic-fixture:visual',
              'signal_to_subject_source': 'synthetic-fixture:target',
              'source_sha256': {name: sha(target / name) for name in
                                ('video_frames.jsonl', 'vehicle_poses.jsonl', 'driver_hand_track.jsonl')}}
    (target / 'hand_signal_review.json').write_text(json.dumps(review, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'frames': len(frames),
                      'review_kind': 'synthetic_diagnostic'}))


if __name__ == '__main__':
    main()
