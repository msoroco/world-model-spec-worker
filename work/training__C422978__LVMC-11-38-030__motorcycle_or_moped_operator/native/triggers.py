"""Candidate selection diagnostics from saved body rows and camera review."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate(case, candidate, saved_rows, visibility_path=None):
    if case not in ('witness_1', 'witness_2') or candidate not in (
            'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown case or fallback')
    if len(saved_rows) != 480 or any(row['frame'] != i for i, row in enumerate(saved_rows)):
        raise ValueError('Saved Native frame sequence differs')
    kinds = {row.get('source_kind') for row in saved_rows}
    if len(kinds) != 1 or kinds.pop() not in ('synthetic_cpu', 'original_native'):
        raise ValueError('Saved source provenance absent')
    native = saved_rows[0]['source_kind'] == 'original_native'
    first_time = float(saved_rows[0].get('time_s', -1))
    if not math.isfinite(first_time) or first_time < 0 or first_time > .2:
        raise ValueError('Saved motorcycle time origin differs')
    overlaps = []
    gaps = []
    prior_native_frame = None
    for frame, row in enumerate(saved_rows):
        time = float(row.get('time_s', -1))
        if (row.get('motorcycle_blueprint') != 'vehicle.kawasaki.ninja' or
                not math.isfinite(time) or
                abs(time - first_time - frame / 20) > 1e-3):
            raise ValueError('Saved motorcycle identity or time differs')
        if native:
            native_frame = row.get('native_frame')
            if (type(native_frame) is not int or
                    (prior_native_frame is not None and native_frame != prior_native_frame + 1)):
                raise ValueError('Saved Native frame sequence differs')
            prior_native_frame = native_frame
        body = row.get('body_native_xy_m' if native else 'body_xy_m')
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError('Saved motorcycle body absent')
        vertices = [(float(v[0]), float(v[1])) for v in body]
        center = row.get('center_native_xy_m' if native else 'center_xy_m')
        if (not isinstance(center, list) or len(center) != 2 or
                len(set(vertices)) != 4 or
                not all(math.isfinite(v) for point in vertices for v in point) or
                abs(sum(x for x, _ in vertices) / 4 - float(center[0])) > .05 or
                abs(sum(y for _, y in vertices) / 4 - float(center[1])) > .05):
            raise ValueError('Saved motorcycle body/center differs')
        ys = [y for _, y in vertices]
        speed = float(row.get('speed_mps', -1))
        if not math.isfinite(speed) or speed < 0:
            raise ValueError('Saved motorcycle speed absent')
        if speed > .1 and ((min(ys) < 5.5 and max(ys) > 3.5) if native else
                            (min(ys) < -3.5 and max(ys) > -5.5)):
            overlaps.append(row['frame'])
        gaps.append(3.5 - max(ys) if native else min(ys) + 3.5)
    if candidate == 'fallback1':
        value = (overlaps[0] if overlaps else None) if case == 'witness_2' else len(overlaps)
        threshold = 90 if case == 'witness_2' else 0
        triggered = value is None or value > threshold
        method = 'first moving full-body sidewalk overlap frame' if case == 'witness_2' else 'unwanted moving sidewalk overlap frames'
    elif candidate == 'fallback2':
        value = len(overlaps) if case == 'witness_2' else min(gaps)
        threshold = 380 if case == 'witness_2' else 1.0
        triggered = value < threshold
        method = 'moving sidewalk overlap frame count' if case == 'witness_2' else 'minimum full-body roadway-to-sidewalk gap m'
    else:
        if visibility_path is None:
            raise ValueError('Original camera visibility packet absent')
        packet = json.loads(Path(visibility_path).read_text())
        video = Path(visibility_path).parent / packet['video_path']
        if not video.is_file() or sha(video) != packet.get('video_sha256'):
            raise ValueError('Camera source hash differs')
        if packet.get('case_suffix') != case or packet.get('source_kind') != saved_rows[0]['source_kind']:
            raise ValueError('Camera review provenance differs')
        value = float(packet['visible_fraction'])
        if not math.isfinite(value) or value < 0 or value > 1:
            raise ValueError('Camera visible fraction invalid')
        threshold = .75
        triggered = value < threshold
        method = 'source-hashed original camera motorcycle visible fraction'
    return {'case_suffix': case, 'candidate_id': candidate,
            'method': method, 'value': value, 'threshold': threshold,
            'triggered': triggered,
            'source_kind': saved_rows[0]['source_kind'],
            'legal_outcome_claimed': False}
