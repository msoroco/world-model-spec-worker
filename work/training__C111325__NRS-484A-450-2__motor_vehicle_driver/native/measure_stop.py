"""Source-only diagnostic for a full halt before the near-side crosswalk.

Speed and body-position tolerances are engineering measurements, not legal thresholds.
"""
from pathlib import Path
import hashlib
import json
import math
import xml.etree.ElementTree as ET

FRAMES = 600
RATE_HZ = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(root, expected_case):
    root = Path(root)
    for name in ('road.xodr', 'native_samples.jsonl'):
        if not (root / name).is_file():
            raise ValueError('Missing required source: ' + name)
    manifest_path = root / 'diagnostic-source-manifest.json'
    if not manifest_path.is_file() and (root / 'source-manifest.json').is_file():
        manifest_path = root / 'source-manifest.json'
    if not manifest_path.is_file():
        raise ValueError('Missing required source: diagnostic-source-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    source_kind = manifest.get('source_kind')
    if manifest.get('case_id') != expected_case or source_kind not in (
            'synthetic_native_sample', 'native_observation'):
        raise ValueError('Diagnostic source identity differs')
    for name in ('road.xodr', 'native_samples.jsonl'):
        if manifest.get('sha256', {}).get(name) != sha(root / name):
            raise ValueError('Saved source hash differs: ' + name)
    road = next((r for r in ET.parse(root / 'road.xodr').getroot().findall('road')
                 if r.get('id') == '1'), None)
    if road is None or not any(s.get('name') == 'STOP' for s in road.findall('signals/signal')):
        raise ValueError('Governing stop sign absent from source road')
    crossings = [o for o in road.findall('objects/object') if o.get('type') == 'crosswalk']
    if len(crossings) != 1 or not 224 <= float(crossings[0].get('s', -1)) <= 226:
        raise ValueError('Near-side crosswalk absent from source road')
    rows = [json.loads(line) for line in (root / 'native_samples.jsonl').read_text().splitlines()]
    if len(rows) != FRAMES:
        raise ValueError('Full 600-frame source window absent')
    first_crossing = None
    first_intersection = None
    halted_before_crossing = []
    first_native_frame = rows[0].get('native_frame')
    first_time = rows[0].get('time_s')
    if type(first_native_frame) is not int or not isinstance(first_time, (int, float)):
        raise ValueError('Original Native frame/time start absent')
    for index, row in enumerate(rows):
        expected_native_frame = 100 + index if source_kind == 'synthetic_native_sample' else first_native_frame + index
        expected_time = index / RATE_HZ if source_kind == 'synthetic_native_sample' else first_time + index / RATE_HZ
        if row.get('video_frame') != index or row.get('native_frame') != expected_native_frame \
                or not math.isclose(row.get('time_s', -1), expected_time, abs_tol=1e-5):
            raise ValueError('Original frame/time join differs')
        if row.get('source_kind') != source_kind or row.get('road_id') not in (1, 13, 4) \
                or row.get('lane_id') != -1:
            raise ValueError('Native approach road/lane role differs')
        vertices = row.get('body_vertices_m')
        if not isinstance(vertices, list) or len(vertices) != 8 \
                or any(not isinstance(v, list) or len(v) != 3 or
                       any(not isinstance(c, (int, float)) or not math.isfinite(c) for c in v)
                       for v in vertices):
            raise ValueError('Full original Native body absent')
        speed = row.get('speed_mps')
        if not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
            raise ValueError('Finite original Native speed absent')
        front = max(v[1] for v in vertices)
        if first_crossing is None:
            if front >= -11:
                first_crossing = index
            elif speed <= .15 and front < -11:
                halted_before_crossing.append(index)
        if first_intersection is None and front >= -7:
            first_intersection = index
    if first_crossing is None or first_intersection is None \
            or first_crossing >= first_intersection:
        raise ValueError('Crosswalk/intersection entry sequence absent')
    run = best = 0
    for index in range(first_crossing):
        if index in halted_before_crossing:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return {'format': 'c111325-crosswalk-stop-diagnostic-v1', 'case_id': expected_case,
            'frames': FRAMES, 'rate_hz': RATE_HZ, 'source_kind': source_kind,
            'source_hashes': {n: sha(root / n) for n in ('road.xodr', 'native_samples.jsonl')},
            'first_crosswalk_body_frame': first_crossing,
            'first_intersection_body_frame': first_intersection,
            'longest_pre_crosswalk_stop_frames': best,
            'pre_crosswalk_full_halt_observed': best >= 20,
            'stop_sign_physically_verified': False,
            'crosswalk_physically_verified': False,
            'legal_verdict': None, 'physical_observation_claimed': False}
