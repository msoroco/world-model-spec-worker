"""Measure candidate NRS 484B.650(1) event windows from original sources.

Input event labels are cited review hypotheses. This code checks their timing and
path span; it does not decide any predicate violation or immediate-hazard law.
"""

from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


MILE_M = 1609.344
PREDICATES = {'device', 'off_pavement_right_pass', 'marked_lane',
              'too_close', 'yield'}
CATEGORIES = PREDICATES | {'speed', 'hazard'}


def _load(path):
    path = Path(path)
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing original source: ' + path.name)
    raw = path.read_bytes()
    try:
        return raw, sha256(raw).hexdigest()
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original source: ' + path.name) from error


def _trace(path):
    raw, digest = _load(path)
    try:
        rows = [json.loads(line) for line in raw.splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid original trace') from error
    if len(rows) < 3:
        raise ValueError('Continuous original driving trace needs three frames')
    cumulative = [0.0]
    previous = None
    for row in rows:
        try:
            frame, time_s = row['frame'], float(row['time_s'])
            x, y = float(row['x_m']), float(row['y_m'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('Original driving frame/position missing') from error
        if type(frame) is not int or not all(isfinite(v) for v in (time_s, x, y)):
            raise ValueError('Original driving frame/position invalid')
        if previous is not None:
            if frame != previous[0] + 1 or abs(time_s - previous[1] - .05) > 1e-4:
                raise ValueError('Original driving trace is not continuous at 20 Hz')
            cumulative.append(cumulative[-1] + hypot(x - previous[2], y - previous[3]))
        previous = frame, time_s, x, y
    return rows, cumulative, digest


def measure(trace_path, event_path, source_root):
    trace, distance, trace_sha = _trace(trace_path)
    raw, event_sha = _load(event_path)
    try:
        events = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid event annotation source') from error
    if not isinstance(events, list):
        raise ValueError('Event annotation source must be a list')
    first = trace[0]['frame']
    roots = Path(source_root).resolve()
    seen, citations = set(), {}
    for event in events:
        if not isinstance(event, dict):
            raise ValueError('Event annotation is not an object')
        category, occurrence = event.get('category'), event.get('occurrence_id')
        frame, ref, digest = event.get('frame'), event.get('source_ref'), event.get('source_sha256')
        if category not in CATEGORIES or not isinstance(occurrence, str) or not occurrence or occurrence in seen:
            raise ValueError('Event category or occurrence identity invalid')
        seen.add(occurrence)
        if type(frame) is not int or frame < first or frame >= first + len(trace):
            raise ValueError('Event outside original continuous driving frames')
        if not isinstance(ref, str) or not ref or not isinstance(digest, str):
            raise ValueError('Event needs a source citation')
        source = (roots / ref).resolve()
        if not source.is_relative_to(roots) or not source.is_file():
            raise ValueError('Event source outside retained source root')
        actual = sha256(source.read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError('Event source hash differs')
        citations[ref] = actual
        if category == 'hazard' and event.get('target_type') not in ('person', 'vehicle'):
            raise ValueError('Hazard target must be a person or vehicle')
    events.sort(key=lambda item: (item['frame'], item['occurrence_id']))
    candidates = []
    for left in range(len(events)):
        speed = hazard = acts = 0
        for right in range(left, len(events)):
            category = events[right]['category']
            speed += category == 'speed'
            hazard += category == 'hazard'
            acts += category in PREDICATES
            start, end = events[left]['frame'], events[right]['frame']
            span_m = distance[end - first] - distance[start - first]
            if span_m > MILE_M:
                break
            if speed and hazard and acts >= 2:
                candidates.append((span_m, start, end, left, right))
                break
    best = min(candidates) if candidates else None
    selected = events[best[3]:best[4] + 1] if best else []
    predicate_categories = [item['category'] for item in selected if item['category'] in PREDICATES]
    return {
        'format': 'worker-aggressive-driving-window-observation',
        'sources': {'driving_trace.jsonl': trace_sha, 'event_annotations.json': event_sha,
                    **citations},
        'original_frame_count': len(trace), 'total_driving_path_m': distance[-1],
        'candidate_window': None if best is None else {
            'start_frame': best[1], 'end_frame': best[2], 'path_m': best[0],
            'event_occurrence_ids': [item['occurrence_id'] for item in selected],
            'predicate_categories': predicate_categories,
            'repeated_predicate_category': len(predicate_categories) > len(set(predicate_categories)),
            'hazard_target_types': [item['target_type'] for item in selected if item['category'] == 'hazard']},
        'predicate_violation_judgments': None,
        'immediate_hazard_legal_judgment': None,
        'aggressive_driving_legal_judgment': None,
    }
