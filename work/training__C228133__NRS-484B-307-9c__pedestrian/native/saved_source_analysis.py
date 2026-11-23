"""Derive C228133 entry measurement from immutable captured and reviewed rows.

The saved processor may add reviewed-source files, but must not alter any
original Native rows supplied by capture or subsequent independent review.
"""

import hashlib
import json
from pathlib import Path
import shutil

from road_entry_measure import measure
from source_review import write_bound_rows


RAW = ('road-boundary.json', 'native-pedestrian-frames.jsonl',
       'video_frames.jsonl')
REVIEWED = ('native-signal-frames.jsonl',
            'native-pedestrian-device-frames.jsonl')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def analyze(attempt, review='independent-review.json'):
    attempt = Path(attempt)
    if not attempt.is_dir():
        raise ValueError('Saved attempt directory missing')
    review_path = attempt / review
    if not review_path.is_file():
        raise ValueError('Independent source review missing')
    original_hashes = {name: digest(attempt / name) for name in RAW + REVIEWED}
    original_hashes[review] = digest(review_path)
    output = attempt / 'reviewed-source'
    count = write_bound_rows(attempt, review_path, output)
    for name in RAW:
        shutil.copyfile(attempt / name, output / name)
    observation = measure(output)
    if observation['frame_count'] != count:
        raise ValueError('Reviewed signal and Native measurement counts differ')
    for name, before in original_hashes.items():
        if digest(attempt / name) != before:
            raise ValueError('Original saved source changed during analysis: ' + name)
    report = {
        'format': 'c228133-saved-source-analysis-v1',
        'measurement': observation,
        'original_source_sha256': original_hashes,
        'reviewed_source_sha256': {
            name: digest(output / name) for name in RAW + REVIEWED},
        'original_native_observed': False,
        'physical_acceptance_claimed': False,
        'legal_verdict': None,
    }
    (output / 'measurement.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
