"""Measure retained body overlap with authored cycle lane at intersection."""
import hashlib
import json
import math
from pathlib import Path

from facility import body_overlap


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def measure(folder):
    context = require(folder, 'facility-context.json')
    body_path = require(folder, 'body-history.jsonl')
    content = json.loads(context.read_text())
    if (content.get('facility_x_m') != [3.5, 5.5] or
            content.get('intersection_y_m') != [-7.0, 7.0] or
            content.get('source_kind') != 'synthetic_cpu_diagnostic' or
            content.get('official_designation_proven') is not False):
        raise ValueError('Facility context differs from authored diagnostic')
    rows = [json.loads(line) for line in body_path.read_text().splitlines() if line.strip()]
    if len(rows) != 600:
        raise ValueError('Expected complete 600-frame source interval')
    overlap = []; inside = []; previous = -1
    for row in rows:
        frame, time = row['native_frame'], row['time_s']
        if type(frame) is not int or frame != previous + 1 or not math.isfinite(time) or abs(time - frame / 20) > 1e-6:
            raise ValueError('Original frame/time join invalid')
        measurement = body_overlap(row)
        if measurement['inside_intersection']:
            inside.append(frame)
        if measurement['cycle_intersection_body_overlap_m2'] > 0:
            overlap.append(frame)
        previous = frame
    if not inside:
        raise ValueError('Body never intersects intersection')
    return {'format': 'c111250-cycle-facility-saved-meter-v1', 'frames': 600,
            'intersection_body_frames': len(inside),
            'cycle_lane_intersection_overlap_frames': len(overlap),
            'first_cycle_lane_intersection_overlap_frame': overlap[0] if overlap else None,
            'source_sha256': {'facility-context.json': sha(context),
                              'body-history.jsonl': sha(body_path)},
            'official_designation_proven': False,
            'subsection_3_exception_resolved': False,
            'legal_verdict_claimed': False}
