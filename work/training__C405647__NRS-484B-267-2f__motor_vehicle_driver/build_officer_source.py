"""Build a source-shaped diagnostic for the officer-direction exception."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
CASE = HERE.name + '__officer_direction'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = HERE / 'current-fixture/controlled_2'
    target = HERE / 'officer-source'
    target.mkdir(exist_ok=True)
    for name in ('video_frames.jsonl', 'vehicle_poses.jsonl'):
        shutil.copyfile(source / name, target / name)
    frames = [json.loads(line) for line in (target / 'video_frames.jsonl').read_text().splitlines()]
    track = []
    for index, frame in enumerate(frames):
        track.append({'video_frame': index, 'native_frame': frame['native_frame'],
                      'actor_id': 109, 'x_m': -30, 'y_m': -4,
                      'direction_active': 100 <= index <= 200,
                      'source_kind': 'synthetic_native_sample'})
    (target / 'officer_track.jsonl').write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in track))
    review = {'case_id': CASE, 'review_kind': 'synthetic_diagnostic',
              'reviewer': 'synthetic diagnostic fixture',
              'officer_actor_id': 109, 'ego_actor_id': 107,
              'directed_otherwise': True, 'directive': 'continue_travel',
              'law_enforcement_identity_source': 'synthetic-fixture:identity',
              'direction_visual_source': 'synthetic-fixture:visual',
              'direction_to_subject_source': 'synthetic-fixture:target',
              'source_sha256': {name: sha(target / name) for name in
                                ('video_frames.jsonl', 'vehicle_poses.jsonl', 'officer_track.jsonl')}}
    (target / 'officer_direction.json').write_text(json.dumps(review, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'frames': len(frames),
                      'review_kind': 'synthetic_diagnostic'}))


if __name__ == '__main__':
    main()
