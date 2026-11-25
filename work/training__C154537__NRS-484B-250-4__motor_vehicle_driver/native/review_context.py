"""Validate a separate human source review against an immutable Native capture.

The review is an annotation, never a rewritten original source. A positive
review remains subject to the independent delivery audit and local acceptance.
"""
import hashlib
import json
from pathlib import Path


SOURCE_FILES = ('capture-seal.json', 'scene-survey.json', 'native-motion.jsonl', 'video_frames.jsonl',
                'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                'driver_reference.mkv')
TOPICS = ('stop_line', 'near_side_crosswalk', 'sidewalk_crosswalk',
          'uncovered_official_signal', 'through_highway', 'driver_view')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(attempt, review):
    attempt = Path(attempt)
    review = json.loads(Path(review).read_text()) if not isinstance(review, dict) else review
    if review.get('format') != 'c154537-source-context-review-v1':
        raise ValueError('Source review format differs')
    if not review.get('reviewer') or not review.get('review_method'):
        raise ValueError('Source review identity and method missing')
    expected = review.get('original_sha256')
    if not isinstance(expected, dict) or set(expected) != set(SOURCE_FILES):
        raise ValueError('Source review original inventory incomplete')
    for name in SOURCE_FILES:
        source = attempt / name
        if not source.is_file() or sha(source) != expected[name]:
            raise ValueError('Source review original hash differs: ' + name)
    original = json.loads((attempt / 'scene-survey.json').read_text())
    if original.get('source_kind') != 'original_native':
        raise ValueError('Source review requires original Native acquisition')
    topics = review.get('topics')
    if not isinstance(topics, dict) or set(topics) != set(TOPICS):
        raise ValueError('Source review topics incomplete')
    for topic, item in topics.items():
        if not isinstance(item, dict) or item.get('status') not in ('confirmed', 'rejected', 'unresolved'):
            raise ValueError('Source review disposition missing: ' + topic)
        refs = item.get('source_refs')
        if not isinstance(refs, list) or not refs or not set(refs) <= set(SOURCE_FILES):
            raise ValueError('Source review reference missing: ' + topic)
        if not item.get('observation') or not item.get('reason'):
            raise ValueError('Source review observation missing: ' + topic)
    # A source-bound review records observations; it does not turn uncertain
    # human judgments into automatic compliance findings.
    return {'format': 'c154537-reviewed-source-context-v1',
            'review_sha256': hashlib.sha256(json.dumps(review, sort_keys=True).encode()).hexdigest(),
            'confirmed_topics': sorted(k for k, v in topics.items() if v['status'] == 'confirmed'),
            'unresolved_topics': sorted(k for k, v in topics.items() if v['status'] == 'unresolved'),
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
