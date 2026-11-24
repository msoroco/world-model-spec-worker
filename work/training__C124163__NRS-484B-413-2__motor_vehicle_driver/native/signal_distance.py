"""Measure continuously observed turn signal distance from retained rows.

The diagnostic sources here are synthetic. Numeric 100/300-foot distances come
from the statute; a CPU fixture cannot establish physical activation or legal
compliance of an original Native vehicle.
"""
import hashlib
import json
import math
from pathlib import Path

HZ = 20
FRAMES = 600
FEET_TO_METRES = 0.3048
DISTRICTS = {'business_or_residential': 100, 'other_area': 300}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(source):
    source = Path(source)
    index = json.loads((source / 'source-index.json').read_text())
    if index.get('format') != 'c124163-signal-distance-source-v1':
        raise ValueError('source index format differs')
    if set(index.get('files', {})) != {'native-samples.jsonl', 'context.json'}:
        raise ValueError('source inventory incomplete')
    for name, expected in index['files'].items():
        path = source / name
        if not path.is_file() or sha(path) != expected:
            raise ValueError('source hash mismatch: ' + name)
    context = json.loads((source / 'context.json').read_text())
    rows = [json.loads(line) for line in (source / 'native-samples.jsonl').read_text().splitlines()]
    return index, context, rows


def measure(source):
    index, context, rows = load(source)
    district = context.get('district_class')
    if district not in DISTRICTS or context.get('source_kind') != 'synthetic_native_sample':
        raise ValueError('district/source context missing')
    if context.get('weather') not in ('clear', 'rain') or len(rows) != FRAMES:
        raise ValueError('weather or 600-frame source missing')
    if index.get('frames') != FRAMES or index.get('rate_hz') != HZ:
        raise ValueError('source frame contract changed')
    turns = []
    previous_distance = None
    for frame, row in enumerate(rows):
        traveled = row.get('odometer_native_m')
        if (row.get('frame') != frame or row.get('time_s') != frame / HZ or
                row.get('source_kind') != 'synthetic_native_sample' or
                type(traveled) not in (int, float) or not math.isfinite(traveled) or
                (previous_distance is not None and traveled < previous_distance) or
                type(row.get('signal_visible')) is not bool or
                type(row.get('course_change_started')) is not bool):
            raise ValueError('Native frame/time/odometer/signal join failed')
        previous_distance = traveled
        if row['course_change_started']:
            turns.append(frame)
    if len(turns) != 1:
        raise ValueError('exactly one course-change onset required')
    turn = turns[0]
    if turn == 0 or not rows[turn]['signal_visible']:
        raise ValueError('signal absent at course-change onset')
    start = turn
    while start > 0 and rows[start - 1]['signal_visible']:
        start -= 1
    distance = rows[turn]['odometer_native_m'] - rows[start]['odometer_native_m']
    if distance < 0:
        raise ValueError('negative signal distance')
    required = DISTRICTS[district] * FEET_TO_METRES
    return {
        'format': 'c124163-source-signal-distance-measurement-v1',
        'condition': index['condition'], 'source_index_sha256': sha(Path(source) / 'source-index.json'),
        'source_hashes': index['files'], 'frames': FRAMES, 'rate_hz': HZ,
        'district_class_source': district, 'weather_source': context['weather'],
        'signal_continuous_start_frame': start, 'course_change_frame': turn,
        'continuous_signal_distance_m': round(distance, 3),
        'statutory_distance_ft': DISTRICTS[district],
        'statutory_distance_m': round(required, 3),
        'synthetic_numeric_distance_met': distance + 1e-6 >= required,
        'weather_waiver_applied': False,
        'original_native_observed': False, 'legal_verdict_claimed': False,
    }
