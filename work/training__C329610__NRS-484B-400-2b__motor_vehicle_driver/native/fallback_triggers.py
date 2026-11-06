"""CPU evaluation of proposed fallback triggers from saved original-source rows.

These engineering thresholds select a construction retry; they are not legal
thresholds and synthetic results do not assert Native behavior or pixel quality.
"""
import hashlib
import json
import math
from pathlib import Path


def _rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing trigger source: ' + path.name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Empty trigger source: ' + path.name)
    return rows, hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Invalid trigger value: ' + name)
    return float(value)


def evaluate(candidate, *, samples_path=None, geometry_path=None,
             pixel_audit_path=None, video_path=None, requested_exit_x_m=None):
    """Return measured retry decision with exact source hashes.

    fallback1: no sampled complete destination exit by 24 s.
    fallback2: peak destination x tracking error in the turn window > .35 m.
    fallback3: body and centreline jointly visible on <95% of exit frames.
    """
    if candidate not in ('fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown fallback trigger')
    sources = {}
    if candidate in ('fallback1', 'fallback2'):
        samples, sources['native_samples.jsonl'] = _rows(samples_path)
        geometry = Path(geometry_path)
        if not geometry.is_file():
            raise ValueError('Missing trigger source: road_geometry.json')
        sources['road_geometry.json'] = hashlib.sha256(geometry.read_bytes()).hexdigest()
        previous = -math.inf
        for sample in samples:
            time = _number(sample['time_s'], 'time_s')
            if time <= previous or time > 24.05:
                raise ValueError('Invalid original sample time order or duration')
            previous = time
        if len(samples) != 480 or abs(previous-24) > .051:
            raise ValueError('Trigger requires complete 480-frame, 24 s source')
        if candidate == 'fallback1':
            from measure_exit import measure
            try:
                result = measure(samples_path, geometry_path)
            except ValueError as exc:
                if str(exc) != 'No full-body destination exit with observed turn completion':
                    raise
                completed = False
            else:
                completed = result['full_body_exit_observed']
            value = 0 if completed else 1
            threshold = 0
            unit = 'missing full-body destination exit by 24 s'
        else:
            _number(requested_exit_x_m, 'requested_exit_x_m')
            observed = [_number(row['controller_request']['route_error_m'], 'route_error_m')
                        for row in samples
                        if -5 <= _number(row['native_center_xy_m'][1], 'native y') <= 5]
            if not observed:
                raise ValueError('No Native turn-window samples for tracking trigger')
            if any(x < 0 for x in observed):
                raise ValueError('Negative controller route error')
            value = max(observed)
            threshold = .35
            unit = 'metres peak controller nearest-route error in y=-5..5 m window'
    else:
        rows, sources['pixel_audit.jsonl'] = _rows(pixel_audit_path)
        video = Path(video_path)
        if not video.is_file():
            raise ValueError('Missing original source video')
        sources[video.name] = hashlib.sha256(video.read_bytes()).hexdigest()
        expected = sources[video.name]
        frames = []
        for row in rows:
            if row.get('source_video_sha256') != expected:
                raise ValueError('Pixel audit is not bound to original source video')
            frame = row.get('video_frame')
            if type(frame) is not int or frame < 0 or frame in frames:
                raise ValueError('Invalid pixel audit frame identity')
            if type(row.get('body_visible')) is not bool or type(row.get('centerline_visible')) is not bool:
                raise ValueError('Missing inspected pixel visibility flags')
            frames.append(frame)
        if frames != list(range(frames[0], frames[-1]+1)):
            raise ValueError('Pixel audit exit window has gaps')
        value = sum(row['body_visible'] and row['centerline_visible'] for row in rows)/len(rows)
        threshold = .95
        unit = 'fraction of exit-window frames with body and centreline visible'
    triggered = value > threshold if candidate != 'fallback3' else value < threshold
    return {'format': 'c329610-fallback-trigger-cpu-v1', 'candidate_id': candidate,
            'measured_value': value, 'threshold': threshold, 'unit': unit,
            'triggered': triggered, 'source_sha256': sources,
            'scope': 'saved-source engineering retry decision; synthetic fixtures are not physical observations'}
