"""Derive C228133 entry measurement from immutable captured and reviewed rows.

The saved processor may add reviewed-source files, but must not alter any
original Native rows supplied by capture or subsequent independent review.
"""

import hashlib
import json
from pathlib import Path
import shutil

from road_entry_measure import measure
from source_review import bind, write_bound_rows


RAW = ('road-boundary.json', 'native-pedestrian-frames.jsonl',
       'video_frames.jsonl', 'governing-device-authority.json',
       'highway-authority.json')
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
    provenance_path = attempt / 'acquisition-provenance.json'
    provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
    diagnostic_fixture = provenance.get('provenance_kind') == 'synthetic_fixture' and \
        provenance.get('diagnostic_fixture') is True and \
        provenance.get('native_executed') is False
    if provenance and not diagnostic_fixture and provenance.get('provenance_kind') != 'native':
        raise ValueError('Unrecognized saved-source provenance')
    for name in RAW + REVIEWED:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    original_hashes = {name: digest(attempt / name) for name in RAW + REVIEWED}
    original_hashes[review] = digest(review_path)
    output = attempt / 'reviewed-source'
    if output.exists():
        signals, devices = bind(attempt, review_path, diagnostic_fixture)
        for name, rows in (('native-signal-frames.jsonl', signals),
                           ('native-pedestrian-device-frames.jsonl', devices)):
            expected = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows)
            if (output / name).read_text() != expected:
                raise ValueError('Retained reviewed source differs from original review: ' + name)
        for name in RAW:
            if digest(output / name) != original_hashes[name]:
                raise ValueError('Retained original Native source differs: ' + name)
        count = len(signals)
    else:
        count = write_bound_rows(attempt, review_path, output, diagnostic_fixture)
        for name in RAW:
            shutil.copyfile(attempt / name, output / name)
    observation = measure(output, diagnostic_fixture)
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
        'diagnostic_fixture': diagnostic_fixture,
        'physical_acceptance_claimed': False,
        'legal_verdict': None,
    }
    measurement_path = output / 'measurement.json'
    if measurement_path.exists():
        if json.loads(measurement_path.read_text()) != report:
            raise ValueError('Retained source measurement differs from replayed analysis')
    else:
        measurement_path.write_text(json.dumps(report, indent=2) + '\n')
    return report
