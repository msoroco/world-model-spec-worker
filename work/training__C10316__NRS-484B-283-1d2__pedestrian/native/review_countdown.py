"""Check an independent original-frame review of a Native countdown crossing.

The review is written after capture and binds the immutable source files. The
checker validates its joins and explicit observations; only an actual reviewer
can establish whether the displayed symbols and digits are legible.
"""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def validate(folder, context, samples):
    folder = Path(folder)
    review_path = folder / 'countdown-original-review.json'
    required = ('countdown-original-review.json', 'driver_reference.mkv',
                'video_frames.jsonl', 'countdown_samples.jsonl', 'road.xodr',
                'capture/manifest.json')
    for name in required:
        if not (folder / name).is_file():
            raise ValueError('Native countdown review missing source: ' + name)
    capture = json.loads((folder / 'capture/manifest.json').read_text())
    if capture.get('synthetic_diagnostic') is True or capture.get('extraction_confirmed') is not True:
        raise ValueError('Native countdown review cannot use synthetic or incomplete capture')
    review = json.loads(review_path.read_text())
    if (review.get('source_kind') != 'independent_original_pixel_review' or
            review.get('reviewer') in (None, '', 'capture_program') or
            review.get('device_id') != context.get('device_id') or
            review.get('crosswalk_id') != context.get('crosswalk_id')):
        raise ValueError('Native countdown review identity or independence invalid')
    sources = {name: sha(folder / name) for name in required[1:]}
    if review.get('source_sha256') != sources:
        raise ValueError('Native countdown review source hashes differ')
    if any(review.get(key) is not True for key in (
            'governs_crosswalk', 'faces_pedestrian', 'flashing_indication_legible',
            'countdown_digits_legible', 'countdown_accompanies_head')):
        raise ValueError('Native countdown review does not establish a governing legible display')
    mapping = rows(folder / 'video_frames.jsonl')
    observed = review.get('frame_observations')
    if len(mapping) != len(samples) or not isinstance(observed, list) or len(observed) != len(samples):
        raise ValueError('Native countdown review frame coverage incomplete')
    for index, (sample, source, finding) in enumerate(zip(samples, mapping, observed)):
        frame = sample.get('native_frame')
        pixel_hash = source.get('source_rgb_sha256', {}).get('driver_reference')
        if (source.get('video_frame'), source.get('native_frame')) != (index, frame) or \
                pixel_hash != sample.get('original_display_frame_sha256'):
            raise ValueError('Native countdown review original frame join differs')
        if (finding.get('native_frame'), finding.get('original_display_frame_sha256')) != (frame, pixel_hash):
            raise ValueError('Native countdown review original pixel binding differs')
        if (finding.get('observed_indication'), finding.get('observed_illuminated'),
                finding.get('observed_countdown_s')) != (
                sample.get('indication'), sample.get('display_illuminated'),
                sample.get('displayed_countdown_s')):
            raise ValueError('Native countdown review disagrees with source program')
        head = sample.get('native_signal_head')
        expected = 'Red' if sample.get('display_illuminated') else 'Off'
        if (not isinstance(head, dict) or head.get('device_id') != context.get('device_id') or
                head.get('opendrive_id') != '203' or head.get('source') != 'native_actor_readback' or
                head.get('native_state') != expected or
                finding.get('native_actor_id') != head.get('native_actor_id')):
            raise ValueError('Native countdown head actor readback missing or different')
    return {'review_sha256': sha(review_path), 'reviewed_frames': len(samples),
            'source_sha256': sources, 'reviewer': review['reviewer'],
            'governing_legible_countdown_reviewed': True,
            'legal_verdict_claimed': False}
