"""Independently audit the original-camera review record in a saved attempt."""

import hashlib
import json
from pathlib import Path


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt):
    attempt = Path(attempt)
    record_path = attempt / 'channels/original_camera_review.json'
    if not record_path.is_file():
        raise ValueError('Missing original camera review record')
    content = json.loads(record_path.read_text())
    if set(content) != {'original_camera_review'}:
        raise ValueError('Original camera review context differs')
    record = content['original_camera_review']
    mapping_path = attempt / 'video_frames.jsonl'
    frames = [json.loads(line) for line in mapping_path.read_text().splitlines()
              if line.strip()]
    names = ('video_frames.jsonl', *(name + '.mkv' for name in CAMERAS))
    if (record.get('format') != 'original-four-camera-review-index-v1' or
            record.get('cameras') != list(CAMERAS) or
            record.get('frame_count') != len(frames) or not frames or
            record.get('visual_judgment') != 'unreviewed' or
            record.get('legal_judgment') != 'unresolved' or
            set(record.get('source_sha256', {})) != set(names)):
        raise ValueError('Original camera review record contract differs')
    for name in names:
        path = attempt / name
        if not path.is_file() or not path.stat().st_size or sha(path) != record['source_sha256'][name]:
            raise ValueError('Original camera review source differs: ' + name)
    indexed = record.get('frame_index')
    if not isinstance(indexed, list) or len(indexed) != len(frames):
        raise ValueError('Original camera review index length differs')
    prior_frame = -1
    prior_time = float('-inf')
    for index, (source, derived) in enumerate(zip(frames, indexed)):
        frame = source.get('carla_frame')
        time = source.get('time_s')
        if (source.get('video_frame') != index or
                source.get('camera_frames') != {name: frame for name in CAMERAS} or
                not isinstance(frame, int) or isinstance(frame, bool) or frame <= prior_frame or
                not isinstance(time, (int, float)) or isinstance(time, bool) or time <= prior_time or
                derived != {'video_frame': index, 'carla_frame': frame, 'time_s': time}):
            raise ValueError('Original camera review frame identity differs')
        prior_frame, prior_time = frame, time
    return {'format': 'c158196-independent-original-camera-review',
            'frame_count': len(frames), 'source_sha256': record['source_sha256'],
            'review_record_sha256': sha(record_path),
            'visual_judgment': 'unreviewed', 'legal_judgment': 'unresolved',
            'software_audit_passed': True}
