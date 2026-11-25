"""Build a source-bound camera review index without making visual judgments."""

import hashlib
import json
from pathlib import Path


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def build(attempt, frames, source_hashes):
    attempt = Path(attempt)
    if not frames:
        raise ValueError('Original camera review needs frame mapping')
    required = ('video_frames.jsonl', *(name + '.mkv' for name in CAMERAS))
    hashes = {}
    for name in required:
        path = attempt / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing original camera review source: ' + name)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if source_hashes.get(name) != digest:
            raise ValueError('Changed original camera review source: ' + name)
        hashes[name] = digest
    indexed = []
    previous_frame = None
    previous_time = None
    for index, row in enumerate(frames):
        frame = row.get('carla_frame')
        time_s = row.get('time_s')
        camera_frames = row.get('camera_frames')
        if (row.get('video_frame') != index or not isinstance(frame, int) or
                isinstance(frame, bool) or not isinstance(time_s, (int, float)) or
                isinstance(time_s, bool) or camera_frames !=
                {name: frame for name in CAMERAS} or
                (previous_frame is not None and frame <= previous_frame) or
                (previous_time is not None and time_s <= previous_time)):
            raise ValueError('Original four-camera review frame join differs')
        indexed.append({'video_frame': index, 'carla_frame': frame,
                        'time_s': time_s})
        previous_frame, previous_time = frame, time_s
    return {'format': 'original-four-camera-review-index-v1',
            'source_sha256': hashes, 'cameras': list(CAMERAS),
            'frame_count': len(indexed), 'frame_index': indexed,
            'visual_judgment': 'unreviewed', 'legal_judgment': 'unresolved'}


def write(attempt, frames, source_hashes, output):
    record = build(attempt, frames, source_hashes)
    Path(output).write_text(json.dumps({'original_camera_review': record}, sort_keys=True,
                                       allow_nan=False) + '\n')
    return record
