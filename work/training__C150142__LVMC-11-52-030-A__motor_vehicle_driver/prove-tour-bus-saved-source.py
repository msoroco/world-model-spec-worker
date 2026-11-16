"""Run the exact 1,799.95 s saved finalizer on explicit synthetic rows."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__tour_bus_below'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 36120


def materialize(target, package):
    for row in package['files']:
        path = target / row['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(row['content'])
    (target / 'construction.json').write_text(json.dumps(package) + '\n')


def source_rows(target, walker_moves=True):
    config = json.loads((target / 'config.json').read_text())
    target_x = config['requested_target_x_m']
    from_path = target / 'assignment-source.json'
    assignment = json.loads(from_path.read_text())
    (target / 'statutory-context.json').write_text(json.dumps({
        'assignment_id': assignment['assignment_id'], 'law_id': assignment['law_id'],
        'law_text': assignment['law']['text'],
        'law_text_sha256': hashlib.sha256(assignment['law']['text'].encode()).hexdigest()}) + '\n')
    from sys import path
    path.insert(0, str(target))
    try:
        from exception_road import readback
        road = readback((target / 'red-curb-road.xodr').read_text())
    finally:
        path.pop(0)
    (target / 'native-map-readback.json').write_text(json.dumps({
        'source_kind': 'synthetic_native_sample', 'paint_color': 'red',
        'red_curb_start_x_m': 30, 'red_curb_end_x_m': 50, 'curb_y_m': -7,
        'sign_readback': road['sign_readback'],
        'mailbox_readback': road['mailbox_readback']}) + '\n')
    (target / 'capture').mkdir(exist_ok=True)
    with (target / 'native-raw-actors.jsonl').open('w') as actors, \
         (target / 'native-passenger-actors.jsonl').open('w') as passengers, \
         (target / 'video_frames.jsonl').open('w') as frames, \
         (target / 'trace.jsonl').open('w') as trace, \
         (target / 'capture/evidence.jsonl').open('w') as evidence:
        for i in range(FRAMES):
            x = target_x * min(i, 120) / 120
            y = -6.8
            t = i / 20
            walker_y = (-10 + min(max(i - 120, 0), 60) * .05
                        if walker_moves else -10)
            actor = {'frame': i, 'native_frame': i, 'time_s': t,
                     'source_kind': 'synthetic_native_sample',
                     'actor_id': 1, 'blueprint': 'vehicle.mitsubishi.fusorosa',
                     'ego_center_native_xy_m': [x, y],
                     'ego_body_native_xy_m': [[x - 1, y - .5], [x + 1, y - .5],
                                              [x + 1, y + .5], [x - 1, y + .5]],
                     'velocity_native_xyz_mps': [1 if i < 120 else 0, 0, 0],
                     'yaw_deg': 0}
            walker = {'frame': i, 'native_frame': i, 'time_s': t,
                      'source_kind': 'synthetic_native_sample', 'actor_id': 2,
                      'blueprint': 'walker.pedestrian.0001',
                      'center_native_xy_m': [target_x, walker_y],
                      'velocity_native_xyz_mps': [0, 1 if 120 <= i < 180 else 0, 0]}
            frame = {'video_frame': i, 'native_frame': i, 'carla_frame': i,
                     'time_s': t, 'views': list(VIEWS)}
            actors.write(json.dumps(actor) + '\n')
            passengers.write(json.dumps(walker) + '\n')
            frames.write(json.dumps(frame) + '\n')
            trace.write(json.dumps({'frame': i, 'time_s': t,
                                    'position_m': [x, y, 0],
                                    'speed_mps': 1 if i < 120 else 0}) + '\n')
            evidence.write(json.dumps({'frame': i,
                                       'source_kind': 'synthetic_native_sample'}) + '\n')
    for view in VIEWS:
        (target / (view + '.mkv')).write_bytes(b'synthetic placeholder; not decoded')


def run(target):
    env = __import__('os').environ.copy()
    env['PYTHONPATH'] = str(REPO / 'runtime/pipeline/scenario_pipeline')
    return subprocess.run([sys.executable, str(target / 'finalize_selected.py'),
        '--attempt', str(target), '--output', str(target / 'analysis-report.json')],
        cwd=target, env=env, text=True, capture_output=True)


def prove(candidate='primary', negatives=True):
    if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown tour-bus candidate')
    package_path = (ROOT / 'selected-primary/tour_bus_below/construction.json' if
                    candidate == 'primary' else ROOT / 'selected-fallbacks/tour_bus_below' /
                    candidate / 'construction.json')
    package = json.loads(package_path.read_text())
    if package['case_id'] != CASE:
        raise ValueError('Tour-bus construction changed')
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='C150142-tour-bus-saved-') as tmp:
        parent = Path(tmp)
        positive = parent / 'positive'
        materialize(positive, package)
        source_rows(positive)
        result = run(positive)
        if result.returncode:
            raise AssertionError('Long saved finalizer failed: ' + result.stderr[-1500:])
        report = json.loads((positive / 'analysis-report.json').read_text())
        observed = report['measurements']['signed_curb_observation']['value']
        if observed['red_curb_stationary_duration_s'] != 1799.95 or \
           observed['duration_relative_to_30_minutes'] != 'below' or \
           len(observed['recorded_activity_events']) != 1 or \
           observed['legal_verdict'] is not None:
            raise AssertionError('Long source observations differ')
        if negatives:
            negative = parent / 'missing-walker'
            materialize(negative, package)
            for name in ('statutory-context.json', 'native-map-readback.json',
                         'native-raw-actors.jsonl'):
                (negative / name).write_text('')
            rejected = run(negative)
            if rejected.returncode == 0 or \
               'Missing required source: native-passenger-actors.jsonl' not in rejected.stderr:
                raise AssertionError('Missing passenger actor source was accepted')
            stationary = parent / 'stationary-walker'
            materialize(stationary, package)
            source_rows(stationary, walker_moves=False)
            rejected_stationary = run(stationary)
            if rejected_stationary.returncode == 0 or \
               'No measured passenger approach at stopped bus' not in rejected_stationary.stderr:
                raise AssertionError('Static passenger actor was accepted as loading')
    return {'case_id': CASE, 'candidate_id': candidate,
            'source_kind': 'synthetic_native_sample',
            'requested_boundary': 'below', 'measured_duration_s': 1799.95,
            'passenger_approach_event': True, 'missing_source_rejected': negatives,
            'stationary_actor_rejected': negatives,
            'media_decoded': False, 'original_native_observed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--skip-negatives', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prove(args.candidate, not args.skip_negatives), sort_keys=True))
