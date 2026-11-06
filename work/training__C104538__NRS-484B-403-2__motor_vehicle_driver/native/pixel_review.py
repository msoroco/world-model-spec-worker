"""Verify frame-by-frame sign/body labels against retained Native camera sources.

Labels are supplied by a reviewer. Synthetic labels test only the saved path.
"""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(samples, mapping, review, video, marks):
    paths = [Path(p) for p in (samples, mapping, review, video, marks)]
    if not all(path.is_file() for path in paths):
        raise ValueError('Missing pixel review source')
    native = [json.loads(line) for line in paths[0].read_text().splitlines() if line.strip()]
    frames = [json.loads(line) for line in paths[1].read_text().splitlines() if line.strip()]
    labels = [json.loads(line) for line in paths[4].read_text().splitlines() if line.strip()]
    packet = json.loads(paths[2].read_text())
    approach = [index for index, sample in enumerate(native)
                if -35 <= float(sample['native_center_xy_m'][0]) <= -10]
    total = packet.get('approach_frames')
    if (len(native) != 480 or len(frames) != 480 or type(total) is not int or
        not 20 <= total <= 480 or len(labels) != total or len(approach) != total):
        raise ValueError('Pixel review coverage incomplete')
    if (packet.get('native_samples_sha256') != sha(paths[0]) or
        packet.get('frame_map_sha256') != sha(paths[1]) or
        packet.get('video_sha256') != sha(paths[3]) or
        packet.get('pixel_review_sha256') != sha(paths[4])):
        raise ValueError('Pixel review source hash mismatch')
    visible = 0
    for index, label in zip(approach, labels):
        sample, frame = native[index], frames[index]
        if (frame.get('video_frame') != index or
            frame.get('native_frame') != sample.get('native_frame') or
            frame.get('carla_frame') != sample.get('native_frame') or
            abs(frame.get('time_s', -1) - sample.get('time_s', -2)) > 1e-6 or
            label.get('video_frame') != index or
            label.get('native_frame') != sample.get('native_frame') or
            type(label.get('full_body_visible')) is not bool or
            type(label.get('sign_visible')) is not bool):
            raise ValueError('Pixel review frame identity or visibility mark invalid')
        visible += label['full_body_visible'] and label['sign_visible']
    if packet.get('full_body_and_sign_visible_frames') != visible:
        raise ValueError('Pixel review count differs from frame marks')
    return {'visible_frames': visible, 'approach_frames': total,
            'visible_fraction': visible / total,
            'source_hashes': {path.name: sha(path) for path in paths}}
