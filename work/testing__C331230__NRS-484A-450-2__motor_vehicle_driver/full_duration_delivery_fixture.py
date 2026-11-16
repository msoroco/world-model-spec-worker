"""900-frame C331230 CPU fixture for saved physical and delivery audit branches.

This generated source is synthetic and stays under .runtime-work. It cannot
establish Native capture, actor visibility, legal status, or physical acceptance.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parent.parent
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from delivery_audit import CAMERAS, audit  # noqa: E402
import delivery_audit as independent_audit  # noqa: E402
from worker_exchange.media import compose_four_views  # noqa: E402
from worker_exchange.native_output import assess_physical  # noqa: E402
from worker_exchange.runtime_cli import execution_env  # noqa: E402

FRAMES = 900
CASE = 'testing__C331230__NRS-484A-450-2__motor_vehicle_driver__marked_crosswalk_stop_before'
SOURCE = REPO / '.runtime-work/c331230-primary-compat-v2'


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False) + '\n')


def position(index):
    if index < 100:
        return 0.0
    if index < 200:
        return 4.0
    return min(24.0, 4.0 + (index - 200) * .1)


def build(attempt):
    if attempt.exists():
        raise ValueError('Use a fresh synthetic fixture root')
    attempt.mkdir(parents=True)
    for name in ('config.json', 'site.json', 'approach_context.json', 'runner.py', 'construction.json'):
        shutil.copy2(SOURCE / name, attempt / name)
    context = json.loads((attempt / 'approach_context.json').read_text())
    write(attempt / 'crosswalk_geometry.json', {
        'intersection_polygon_xy_m': context['intersection_polygon_xy_m'],
        'crosswalk_polygon_xy_m': context['crosswalk_polygon_xy_m'],
        'diagnostic_fixture': True, 'physical_acceptance_claimed': False})
    (attempt / 'capture').mkdir()
    with ((attempt / 'stop_history.jsonl').open('x') as history,
          (attempt / 'video_frames.jsonl').open('x') as mapping,
          (attempt / 'trace.jsonl').open('x') as trace,
          (attempt / 'capture/evidence.jsonl').open('x') as evidence):
        for index in range(FRAMES):
            frame, time = 1000 + index, index / 20
            x = position(index)
            body = [[x-1, -1], [x-1, 1], [x+1, 1], [x+1, -1]]
            history.write(json.dumps({'frame': frame, 'time_s': time, 'road_id': 1,
                'lane_id': -1, 'stop_sign_id': 17, 'ego_speed_mps': 0 if 100 <= index < 200 or index >= 400 else 2,
                'ego_body_vertices_xy_m': body}) + '\n')
            mapping.write(json.dumps({'video_frame': index, 'carla_frame': frame, 'time_s': time}) + '\n')
            trace.write(json.dumps({'frame': frame, 'time_s': time, 'position_m': [x, 0, 0],
                'position': {'x': x, 'y': 0, 'z': 0}, 'heading_deg': 0,
                'speed_mps': 0 if 100 <= index < 200 or index >= 400 else 2}) + '\n')
            evidence.write(json.dumps({'original_frame': frame, 'recording_time_s': time,
                'diagnostic_fixture': True}) + '\n')
    for camera, (width, height) in CAMERAS.items():
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                        '-f', 'lavfi', '-i', f'color=c=black:s={width}x{height}:r=20',
                        '-vf', 'drawbox=x=10:y=10:w=128:h=128:color=red:t=fill',
                        '-frames:v', str(FRAMES), '-an', '-c:v', 'ffv1', '-threads', '2',
                        str(attempt / (camera + '.mkv'))], check=True, timeout=900)
    subprocess.run([sys.executable, str(PACKAGE / 'finalizer.py'), '--attempt', str(attempt),
                    '--output', str(attempt / 'analysis-report.json')],
                   check=True, timeout=120, env=execution_env())
    result = json.loads((attempt / 'result.json').read_text())
    if (result.get('provenance_kind') != 'synthetic_fixture' or
            result.get('physical_acceptance_claimed') is not False or
            any(result['physical_checks'][key]['status'] != 'met'
                for key in ('setup', 'target', 'maneuver'))):
        raise ValueError('Full-duration synthetic physical checker did not pass')
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    write(attempt / 'converted/trace.json', {'scenes': [
        {'t': round(row['time_s'] * 1000)} for row in mapping]})
    receipt = compose_four_views({name: attempt / (name + '.mkv') for name in CAMERAS},
                                 attempt / 'video_frames.jsonl', attempt / 'raw.mkv')
    write(attempt / 'four-view-receipt.json', receipt)
    return result


def prove(attempt):
    result = build(attempt)
    delivery = audit(CASE, attempt, diagnostic=True)
    if (delivery['frames'] != FRAMES or not delivery['software_checks_passed'] or
            delivery['physical_acceptance_claimed'] or delivery['physical_completion_verified']):
        raise ValueError('Synthetic full-duration audit claim differs')
    negative = attempt / 'negative-motion'
    negative.mkdir()
    for name in ('config.json', 'video_frames.jsonl', 'trace.jsonl',
                 'crosswalk_geometry.json', 'approach_context.json', 'result.json'):
        shutil.copy2(attempt / name, negative / name)
    original = (attempt / 'stop_history.jsonl').read_text().splitlines()
    altered = [json.loads(line) for line in original]
    # Keep the last complete body inside the junction: completion must fail.
    for row in altered[400:]:
        row['ego_body_vertices_xy_m'] = [[17, -1], [17, 1], [19, 1], [19, -1]]
    (negative / 'stop_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in altered))
    config = json.loads((attempt / 'config.json').read_text())
    failed = assess_physical(negative, config, result['target_checks'])
    if failed['physical_checks']['maneuver']['status'] == 'met':
        raise ValueError('Incomplete synthetic junction clearance accepted')
    try:
        audit(CASE, negative, diagnostic=True)
    except ValueError as error:
        if 'Missing or changed original source: stop_history.jsonl' not in str(error):
            raise
    else:
        raise ValueError('Changed original motion accepted')
    prove_audit_branches(attempt)
    print(json.dumps({'case_id': CASE, 'frames': FRAMES, 'synthetic_setup': 'met',
                      'synthetic_target': 'met', 'synthetic_maneuver': 'met',
                      'incomplete_clearance': 'rejected', 'changed_original_motion': 'rejected',
                      'four_view_source_sha256': receipt_sources(delivery),
                      'mock_lifecycle_checker': 'passed',
                      'synthetic_pixel_checker': 'passed',
                      'physical_acceptance_claimed': False}, sort_keys=True))


def prove_audit_branches(attempt):
    """Exercise checker branches without writing or claiming Native receipts."""
    mapping_hash = independent_audit.digest(attempt / 'video_frames.jsonl')
    observations = [{'camera': name, 'video_frame': 0,
                     'bbox_xyxy': [0, 0, 128, 128]} for name in CAMERAS]
    independent_audit.verify_pixels(attempt, {'observations': observations}, FRAMES, mapping_hash)
    uniform = [dict(row) for row in observations]
    uniform[0]['bbox_xyxy'] = [200, 200, 264, 264]
    try:
        independent_audit.verify_pixels(attempt, {'observations': uniform}, FRAMES, mapping_hash)
    except ValueError as error:
        if 'Reviewed original pixel ROI has no detail' not in str(error):
            raise
    else:
        raise ValueError('Uniform synthetic pixel region accepted')

    revision = {'construction_sha256': independent_audit.digest(attempt / 'construction.json'),
                'runner_sha256': independent_audit.digest(attempt / 'runner.py')}
    seal = {'format': 'worker-sealed-capture', 'provenance_kind': 'native',
            'diagnostic_fixture': False, 'frames': FRAMES,
            'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
            'restoration': {'restored': True}, 'physical_acceptance_claimed': False,
            'sources': {name: independent_audit.digest(attempt / name)
                        for name in independent_audit.SOURCES},
            'native_revision': revision}
    exit_receipt = {'event': 'native_exit', 'native_revision': revision,
                    'capture_seal_sha256': 'a' * 64}
    owner = {'event': 'owner_released', 'operator_attested': True,
             'native_construction_sha256': revision['construction_sha256'],
             'native_exit_sha256': 'b' * 64}
    mocked = {'capture-seal.json': seal, 'native-exit.json': exit_receipt,
              'owner-release.json': owner}
    fake_hashes = {'capture-seal.json': 'a' * 64, 'native-exit.json': 'b' * 64,
                   'owner-release.json': 'c' * 64}
    original_read, original_digest = independent_audit.read, independent_audit.digest

    def checker_read(path):
        return mocked.get(Path(path).name) or original_read(path)

    def checker_digest(path):
        return fake_hashes.get(Path(path).name) or original_digest(path)

    with patch.object(independent_audit, 'read', checker_read), \
            patch.object(independent_audit, 'digest', checker_digest):
        closure = independent_audit.verify_native_closure(attempt, FRAMES)
        if closure['owner_release_sha256'] != 'c' * 64:
            raise ValueError('Mock closure hash differs')
        owner['native_exit_sha256'] = 'd' * 64
        try:
            independent_audit.verify_native_closure(attempt, FRAMES)
        except ValueError as error:
            if 'Owner release does not bind Native exit' not in str(error):
                raise
        else:
            raise ValueError('Unbound mock owner release accepted')
        owner['native_exit_sha256'] = 'b' * 64
        seal['sources']['stop_history.jsonl'] = 'e' * 64
        try:
            independent_audit.verify_native_closure(attempt, FRAMES)
        except ValueError as error:
            if 'Sealed Native original missing or stale: stop_history.jsonl' not in str(error):
                raise
        else:
            raise ValueError('Stale mock capture seal accepted')


def receipt_sources(delivery):
    return {name: entry['source_sha256'] for name, entry in delivery['camera_decodes'].items()}


def extend_rows(source, destination, name):
    original = [json.loads(line) for line in (source / name).read_text().splitlines() if line.strip()]
    if len(original) != 4:
        raise ValueError('Expected exact four-frame source shape: ' + name)
    history = ([json.loads(line) for line in (destination / 'stop_history.jsonl').read_text().splitlines()]
               if name == 'capture/evidence.jsonl' else None)
    with (destination / name).open('x') as stream:
        for index in range(FRAMES):
            row = json.loads(json.dumps(original[index if index < 4 else -1]))
            frame, time = 100 + index, round(1 + index / 20, 2)
            if name == 'capture/evidence.jsonl':
                row.update(original_frame=frame, replay_frame=frame,
                           recording_time_s=time, replay_simulation_time_s=time)
                observations = row.get('original_observations')
                if observations is not None:
                    observations.update(frame=frame, time_s=time)
                if index >= 4 and observations is not None:
                    measured = history[index]
                    body = measured['ego_body_vertices_xy_m']
                    x = sum(point[0] for point in body) / len(body)
                    vertices = [[point[0], point[1], z] for point in body for z in (0.0, 1.5)]
                    speed = measured['ego_speed_mps']
                    row['ego'].update(position_m=[x, 0, 0], speed_mps=speed, body_vertices_m=vertices)
                    ego = next(participant for participant in observations['participants']
                               if participant['actor_id'] == row['actor_id'])
                    ego.update(position_m=[x, 0, 0], speed_mps=speed,
                               velocity_mps=[speed, 0, 0], body_vertices_m=vertices)
            else:
                row.update(frame=frame, time_s=time)
            if name == 'stop_history.jsonl' and index >= 4:
                row['ego_body_vertices_xy_m'] = [[22, -1], [22, 1], [24, 1], [24, -1]]
                row['ego_speed_mps'] = 0
            elif name == 'trace.jsonl' and index >= 4:
                row['position_m'] = [23, 0, 0]
                row['position'] = {'x': 23, 'y': 0, 'z': 0}
                row['speed_mps'] = 0
            elif name == 'sight_history.jsonl' and index >= 4:
                row['ego_position_xy_m'] = [23, 0]
            stream.write(json.dumps(row, allow_nan=False) + '\n')


def prove_remaining(entry, attempt, media_source):
    if attempt.exists():
        raise ValueError('Use a fresh synthetic fixture root')
    case_id = entry['case_id']
    command = entry['post_capture']['command'].split()
    source = (REPO / command[command.index('--attempt') + 1]).resolve()
    attempt.mkdir(parents=True)
    for name in ('config.json', 'site.json', 'approach_context.json', 'construction.json', 'road.xodr'):
        shutil.copy2(source / name, attempt / name)
    for path in source.glob('*.py'):
        shutil.copy2(path, attempt / path.name)
    context = json.loads((attempt / 'approach_context.json').read_text())
    write(attempt / 'crosswalk_geometry.json', {
        'intersection_polygon_xy_m': context['intersection_polygon_xy_m'],
        'diagnostic_fixture': True, 'physical_acceptance_claimed': False})
    (attempt / 'capture').mkdir()
    for name in ('stop_history.jsonl', 'trace.jsonl', 'capture/evidence.jsonl'):
        extend_rows(source, attempt, name)
    if (source / 'sight_history.jsonl').is_file():
        extend_rows(source, attempt, 'sight_history.jsonl')
    with (attempt / 'video_frames.jsonl').open('x') as mapping:
        for index in range(FRAMES):
            mapping.write(json.dumps({'video_frame': index, 'carla_frame': 100 + index,
                                      'time_s': round(1 + index / 20, 2)}) + '\n')
    for camera in CAMERAS:
        (attempt / (camera + '.mkv')).hardlink_to(media_source / (camera + '.mkv'))
    subprocess.run([sys.executable, str(attempt / 'finalizer.py'), '--attempt', str(attempt),
                    '--output', str(attempt / 'analysis-report.json')],
                   check=True, timeout=120, env=execution_env())
    result = json.loads((attempt / 'result.json').read_text())
    expected_target = ('not_met' if case_id.endswith('__marked_crosswalk_stop_inside') else 'met')
    if (result.get('case_id') != case_id or result.get('provenance_kind') != 'synthetic_fixture' or
            result.get('physical_acceptance_claimed') is not False or
            result['physical_checks']['setup']['status'] != 'met' or
            result['physical_checks']['maneuver']['status'] != 'met' or
            result['physical_checks']['target']['status'] != expected_target):
        raise ValueError('Full-duration synthetic physical checker did not pass: ' + case_id)
    frame_map = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    write(attempt / 'converted/trace.json', {'scenes': [
        {'t': round(row['time_s'] * 1000)} for row in frame_map]})
    receipt = compose_four_views({name: attempt / (name + '.mkv') for name in CAMERAS},
                                 attempt / 'video_frames.jsonl', attempt / 'raw.mkv')
    write(attempt / 'four-view-receipt.json', receipt)
    delivery = audit(case_id, attempt, diagnostic=True)
    if (delivery['frames'] != FRAMES or not delivery['software_checks_passed'] or
            delivery['physical_acceptance_claimed'] or delivery['physical_completion_verified']):
        raise ValueError('Synthetic full-duration audit claim differs: ' + case_id)
    negative = attempt / 'negative-motion'
    negative.mkdir()
    for name in ('config.json', 'video_frames.jsonl', 'trace.jsonl',
                 'crosswalk_geometry.json', 'approach_context.json', 'result.json'):
        shutil.copy2(attempt / name, negative / name)
    with (negative / 'stop_history.jsonl').open('x') as changed:
        for index, line in enumerate((attempt / 'stop_history.jsonl').read_text().splitlines()):
            row = json.loads(line)
            if index >= 4:
                row['ego_body_vertices_xy_m'] = [[17, -1], [17, 1], [19, 1], [19, -1]]
            changed.write(json.dumps(row) + '\n')
    config = json.loads((attempt / 'config.json').read_text())
    if assess_physical(negative, config, result['target_checks'])['physical_checks']['maneuver']['status'] == 'met':
        raise ValueError('Incomplete synthetic junction clearance accepted: ' + case_id)
    try:
        audit(case_id, negative, diagnostic=True)
    except ValueError as error:
        if 'Missing or changed original source: stop_history.jsonl' not in str(error):
            raise
    else:
        raise ValueError('Changed original motion accepted: ' + case_id)
    print(json.dumps({'case_id': case_id, 'frames': FRAMES,
                      'synthetic_setup': 'met', 'synthetic_target': expected_target,
                      'synthetic_maneuver': 'met',
                      'original_cameras': len(delivery['camera_decodes']),
                      'incomplete_clearance': 'rejected', 'changed_source': 'rejected',
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--output-root', type=Path)
    args = parser.parse_args()
    if args.all:
        if not args.output_root:
            parser.error('--all requires --output-root')
        root = args.output_root.resolve()
        if root.exists():
            raise ValueError('Use a fresh synthetic fixture root')
        root.mkdir(parents=True)
        prove(root / 'marked_crosswalk_stop_before')
        manifest = json.loads((PACKAGE / 'execution-manifest.json').read_text())
        for entry in manifest['cases']:
            suffix = entry['case_id'].split('__')[-1]
            if suffix != 'marked_crosswalk_stop_before':
                prove_remaining(entry, root / suffix, root / 'marked_crosswalk_stop_before')
    else:
        if not args.output:
            parser.error('--output required without --all')
        prove(args.output.resolve())
