"""Bind a per-frame pixel review to retained camera video and Native frames.

The review rows are human observations to be made from original pixels later.
Synthetic rows exercise this saved-source contract without asserting visibility.
"""
import hashlib
import json
from pathlib import Path


def sha(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing pixel review source: ' + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing pixel review source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure(samples_path, frame_map_path, video_path, review_path):
    samples, mapping, review = rows(samples_path), rows(frame_map_path), rows(review_path)
    if not samples or len(samples) != len(mapping):
        raise ValueError('Pixel review Native/frame-map count mismatch')
    approach = []
    for index, (sample, frame) in enumerate(zip(samples, mapping)):
        if frame.get('video_frame') != index or frame.get('native_frame') != sample.get('native_frame'):
            raise ValueError('Pixel review frame identity mismatch')
        if abs(float(frame['time_s']) - float(sample['time_s'])) > 1e-4:
            raise ValueError('Pixel review time identity mismatch')
        if -35 <= float(sample['native_center_xy_m'][0]) <= -10:
            approach.append(index)
    if not approach or len(review) != len(approach):
        raise ValueError('Pixel review does not cover every approach frame')
    visible = 0
    for index, mark in zip(approach, review):
        if (mark.get('video_frame') != index or
            mark.get('native_frame') != mapping[index]['native_frame'] or
            type(mark.get('body_visible')) is not bool or
            type(mark.get('centerline_visible')) is not bool):
            raise ValueError('Pixel review row lacks original frame and two visibility marks')
        visible += mark['body_visible'] and mark['centerline_visible']
    return {'source_kind': 'original_camera_pixels',
            'review_method': 'frame_by_frame_body_and_centerline_visibility',
            'source_video_sha256': sha(video_path),
            'frame_map_sha256': sha(frame_map_path),
            'native_samples_sha256': sha(samples_path),
            'review_rows_sha256': sha(review_path),
            'body_and_centerline_visible_frames': visible,
            'approach_frames': len(approach)}


def verify(audit_path, samples_path):
    audit_path = Path(audit_path)
    claimed = json.loads(audit_path.read_text())
    folder = audit_path.parent
    expected = measure(samples_path, folder/'video_frames.jsonl',
                       folder/'approach.mkv', folder/'pixel_review.jsonl')
    if claimed != expected:
        raise ValueError('Pixel review source or count mismatch')
    return expected
