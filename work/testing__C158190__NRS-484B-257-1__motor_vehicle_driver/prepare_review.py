"""Create an unasserted, source-hashed camera review template after capture."""

import argparse
import hashlib
import json
from pathlib import Path

from yield_context import CAMERAS


def prepare(attempt):
    attempt = Path(attempt)
    target = attempt / 'rendered_marking_review.json'
    if target.exists():
        raise ValueError('Retain existing camera review')
    mapping = attempt / 'video_frames.jsonl'
    if not mapping.is_file():
        raise ValueError('Missing original video frame map')
    frames = [json.loads(line) for line in mapping.read_text().splitlines() if line.strip()]
    if not frames or any(row.get('video_frame') != index for index, row in enumerate(frames)):
        raise ValueError('Original video frame map is incomplete')
    for name in CAMERAS:
        if not (attempt / name).is_file():
            raise ValueError('Missing original source camera: ' + name)
    review = {'method': 'original_source_camera_frame_review',
              'reviewer': None,
              'reviewed_frame_count': len(frames),
              'reviewed_carla_frames': [row['carla_frame'] for row in frames],
              'first_carla_frame': frames[0]['carla_frame'],
              'last_carla_frame': frames[-1]['carla_frame'],
              'source_sha256': {name: hashlib.sha256((attempt/name).read_bytes()).hexdigest()
                                for name in CAMERAS},
              'yield_sign_face_visible': None,
              'no_stop_line': None, 'no_near_crosswalk': None,
              'no_police_direction': None,
              'no_traffic_signal_control': None,
              'review_scope_note': 'Inspect every listed original camera frame and Native control inventory; fill findings only after source review. Unknown is not false.'}
    target.write_text(json.dumps(review, indent=2) + '\n')
    return review


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    report = prepare(args.attempt)
    print(json.dumps({'reviewed_frame_count': report['reviewed_frame_count'],
                      'findings_unset': True}))


if __name__ == '__main__':
    main()
