"""Independently verify source isolation and measured CPU contrast; no legal verdict."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
A = HERE / 'current-v2-primary-sources'
B = HERE / 'current-v2-traversal-sources'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def same_except_y(a, b, frame):
    require(len(a) == len(b) and len(a) in (2, 3), 'body point shape changed')
    expected = 3.5 if 400 <= frame <= 450 else 0
    require(abs(a[0] - b[0]) < 1e-9 and abs(b[1] - a[1] - expected) < 1e-9,
            'body point changed beyond prescribed lateral shift')
    if len(a) == 3:
        require(a[2] == b[2], 'body point height changed')


def audit():
    require((A / 'road-context.json').read_bytes() == (B / 'road-context.json').read_bytes(),
            'road context changed')
    require((A / 'video_frames.jsonl').read_bytes() == (B / 'video_frames.jsonl').read_bytes(),
            'timing or video frame map changed')
    fa, fb = records(A / 'vehicle-footprints.jsonl'), records(B / 'vehicle-footprints.jsonl')
    ta, tb = records(A / 'trace.jsonl'), records(B / 'trace.jsonl')
    ea, eb = records(A / 'capture/evidence.jsonl'), records(B / 'capture/evidence.jsonl')
    require(len(fa) == len(fb) == len(ta) == len(tb) == len(ea) == len(eb) == 600,
            'incomplete comparison interval')
    changed = []
    for frame, (f0, f1, t0, t1, e0, e1) in enumerate(zip(fa, fb, ta, tb, ea, eb)):
        require(f0['native_frame'] == f1['native_frame'] == t0['frame'] == t1['frame'] == frame,
                'frame identity changed')
        require(f0['time_s'] == f1['time_s'] == t0['time_s'] == t1['time_s'] == frame / 20,
                'frame time changed')
        for p0, p1 in zip(f0['body_xy_m'], f1['body_xy_m']):
            same_except_y(p0, p1, frame)
        same_except_y(t0['position_m'], t1['position_m'], frame)
        require(t0['position']['x'] == t1['position']['x'] and
                abs(t1['position']['y'] - t0['position']['y'] -
                    (3.5 if 400 <= frame <= 450 else 0)) < 1e-9,
                'trace position changed beyond lateral shift')
        require(t0['speed_mps'] == t1['speed_mps'] and t0['control'] == t1['control'],
                'speed or control changed')
        require(t1.get('velocity_mps') == [t0['speed_mps'], 0.0, 0.0],
                'traversal original velocity conflicts with source speed')
        same_except_y(e0['ego']['position_m'], e1['ego']['position_m'], frame)
        for p0, p1 in zip(e0['ego']['body_vertices_m'], e1['ego']['body_vertices_m']):
            same_except_y(p0, p1, frame)
        require(e0['world']['weather'] == e1['world']['weather'], 'weather changed')
        expected_lane = 1 if 400 <= frame <= 450 else -1
        require(e0['world']['road_projection']['lane_id'] == -1 and
                e1['world']['road_projection']['lane_id'] == expected_lane,
                'lane readback contrast changed')
        if expected_lane == 1:
            changed.append(frame)
    reports = [json.loads((HERE / name).read_text()) for name in
               ('current-v2-primary-analysis-report.json',
                'current-v2-traversal-analysis-report.json')]
    values = [report['measurements']['zone_measurement']['value'] for report in reports]
    require(values[0]['first_left_active_frame'] is None and
            values[1]['first_left_approach_frame'] is None and
            values[1]['first_left_traversal_frame'] is not None,
            'measured left-side contrast absent')
    require(values[0]['one_way_highway'] is False and values[1]['one_way_highway'] is False,
            'one-way applicability changed')
    for name in ('primary', 'traversal'):
        compatibility = json.loads((HERE / f'current-v2-{name}-compatibility.json').read_text())
        saved = json.loads((HERE / f'current-v2-{name}-saved-processing.json').read_text())
        require(compatibility['passed'] and compatibility['negative_removed'] == 'vehicle-footprints.jsonl',
                'public compatibility or negative proof absent')
        require(saved['passed'] and saved['recorded_only'] and not saved['missing_evidence'],
                'recorded-only processing absent')
    return {'format': 'c111250-unselected-traversal-comparison-audit-v1', 'passed': True,
            'frames': 600, 'lateral_change_first': changed[0],
            'lateral_change_last': changed[-1], 'lateral_change_frames': len(changed),
            'primary_first_left_active': values[0]['first_left_active_frame'],
            'traversal_first_left_approach': values[1]['first_left_approach_frame'],
            'traversal_first_left_traversal': values[1]['first_left_traversal_frame'],
            'road_context_sha256': sha(A / 'road-context.json'),
            'frame_map_sha256': sha(A / 'video_frames.jsonl'),
            'source_kind': 'synthetic_cpu_diagnostic', 'selected': False,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    result = audit()
    target = HERE / 'current-v2-traversal-comparison-audit.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
