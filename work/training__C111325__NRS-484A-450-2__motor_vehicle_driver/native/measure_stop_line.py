"""Source-only measurement of the no-crosswalk, marked-line alternative."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(root, case_id):
    root = Path(root)
    needed = ('road.xodr', 'native_samples.jsonl', 'diagnostic-source-manifest.json')
    for name in needed:
        if not (root / name).is_file():
            raise ValueError('Missing required source: ' + name)
    manifest = json.loads((root / 'diagnostic-source-manifest.json').read_text())
    kind = manifest.get('source_kind')
    if manifest.get('case_id') != case_id or kind not in ('native_observation', 'synthetic_native_sample'):
        raise ValueError('Marked-line source identity differs')
    for name in needed[:2]:
        if manifest.get('sha256', {}).get(name) != sha(root / name):
            raise ValueError('Marked-line saved source hash differs: ' + name)
    road = next((r for r in ET.parse(root / 'road.xodr').getroot().findall('road')
                 if r.get('id') == '1'), None)
    if road is None or not any(s.get('name') == 'STOP' for s in road.findall('signals/signal')):
        raise ValueError('Governing stop sign absent from source road')
    objects = road.findall('objects/object')
    if any(o.get('type') == 'crosswalk' for o in objects):
        raise ValueError('Marked-line alternative has a crosswalk')
    lines = [o for o in objects if o.get('name') == 'clearly_marked_stop_line'
             and o.get('type') == 'roadMark']
    if len(lines) != 1 or not 228 <= float(lines[0].get('s', -1)) <= 230:
        raise ValueError('Clearly marked stop-line source absent')
    boundary_y = float(lines[0].get('s')) - 240.0
    rows = [json.loads(line) for line in (root / 'native_samples.jsonl').read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Full 600-frame marked-line source window absent')
    start_frame, start_time = rows[0].get('native_frame'), rows[0].get('time_s')
    if type(start_frame) is not int or not isinstance(start_time, (int, float)):
        raise ValueError('Original Native frame/time start absent')
    first_line = first_intersection = None
    halted = set()
    for index, row in enumerate(rows):
        frame = 100 + index if kind == 'synthetic_native_sample' else start_frame + index
        time = index / 20 if kind == 'synthetic_native_sample' else start_time + index / 20
        if (row.get('native_frame') != frame or row.get('video_frame') != index
                or not math.isclose(row.get('time_s', -1), time, abs_tol=1e-5)):
            raise ValueError('Original marked-line frame/time join differs')
        if row.get('source_kind') != kind or row.get('lane_id') != -1 or row.get('road_id') not in (1, 13, 4):
            raise ValueError('Signed approach lane source differs')
        vertices = row.get('body_vertices_m')
        if not isinstance(vertices, list) or len(vertices) != 8 or any(
                not isinstance(v, list) or len(v) != 3 or any(
                    not isinstance(c, (int, float)) or not math.isfinite(c) for c in v)
                for v in vertices):
            raise ValueError('Original full vehicle body absent')
        speed = row.get('speed_mps')
        if not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
            raise ValueError('Original finite speed absent')
        front = max(v[1] for v in vertices)
        if first_line is None:
            if front >= boundary_y:
                first_line = index
            elif speed <= .15:
                halted.add(index)
        if first_intersection is None and front >= -7:
            first_intersection = index
    if first_line is None or first_intersection is None or first_line >= first_intersection:
        raise ValueError('Stop-line/intersection entry sequence absent')
    run = best = 0
    for index in range(first_line):
        run = run + 1 if index in halted else 0
        best = max(best, run)
    return {'format': 'c111325-marked-line-source-measurement-v1',
            'case_id': case_id, 'source_kind': kind, 'frames': len(rows),
            'source_hashes': {name: sha(root / name) for name in needed[:2]},
            'first_stop_line_body_frame': first_line,
            'first_intersection_body_frame': first_intersection,
            'longest_pre_line_halt_frames': best,
            'pre_line_full_halt_observed': best >= 20,
            'physical_line_appearance_verified': False,
            'legal_verdict': None}
