"""Run the pinned portable package path on an exact C405647 CPU diagnostic."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
sys.path.insert(0, str(HERE / 'native'))
from geometry import open_drive
from traffic_spec_adapter.adapter import load_graph
from worker_exchange.media import compose_four_views
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env

spec = importlib.util.spec_from_file_location('saved_finalization_fixture',
                                              HERE / 'prove-saved-finalization.py')
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def _write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def build(source, case, ffmpeg):
    source.mkdir()
    fixture_module._fixture(source, case, ffmpeg, full_resolution=True)
    (source / 'road.xodr').write_text(open_drive())
    actor_rows = _rows(source / 'observed-actors.jsonl')
    trace = _rows(source / 'trace.jsonl')
    mapping = _rows(source / 'video_frames.jsonl')
    evidence, frames, participants = [], [], []
    graph_source = ROOT / 'runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl'
    graph = load_graph(graph_source)
    if 'observed_actor_108' in graph:
        graph.remove_node('observed_actor_108')
    graph_dir = source / 'capture/native/graphs/base'
    graph_dir.mkdir(parents=True)
    for index, (actor, point, frame) in enumerate(zip(actor_rows, trace, mapping)):
        native_frame = frame['native_frame']
        centre = actor['actors']['subject']['native_center_xy_m']
        next_actor = actor_rows[min(index + 1, len(actor_rows) - 1)]
        previous_actor = actor_rows[max(index - 1, 0)]
        dt = next_actor['time_s'] - previous_actor['time_s']
        if not dt:
            raise ValueError('Degenerate synthetic actor time step')
        velocity = {}
        for role in ('subject', 'approach'):
            after = next_actor['actors'][role]['native_center_xy_m']
            before = previous_actor['actors'][role]['native_center_xy_m']
            vx, vy = (after[0] - before[0]) / dt, (after[1] - before[1]) / dt
            velocity[role] = [vx, vy, 0.0]
        subject_speed = sum(v * v for v in velocity['subject']) ** .5
        point['position'] = {'x': centre[0], 'y': centre[1], 'z': .5}
        point['position_m'] = [centre[0], centre[1], .5]
        point['speed_mps'] = subject_speed
        point['speed_mph'] = subject_speed / .44704
        point['velocity_mps'] = velocity['subject']
        point['control'] = {'throttle': .3, 'brake': 0.0, 'hand_brake': False}
        body = [[x, y, z] for x, y in actor['actors']['subject']['native_body_xy_m']
                for z in (0, 1.5)]
        approach_centre = actor['actors']['approach']['native_center_xy_m']
        approach_body = [[approach_centre[0] + dx, approach_centre[1] + dy, z]
                         for dx in (-2.25, 2.25) for dy in (-.9, .9)
                         for z in (0, 1.5)]
        actor_packets = {}
        for role, aid, vertices in (('subject', 107, body),
                                    ('approach', 108, approach_body)):
            actor_packets[role] = {'actor_id': aid, 'blueprint': 'vehicle.lincoln.mkz_2020',
                                   'body_vertices_m': vertices, 'heading_deg': 0.0,
                                   'velocity_mps': velocity[role],
                                   'speed_mps': sum(v * v for v in velocity[role]) ** .5,
                                   'accel_longitudinal_mps2': 0.0}
        participants.append({'time_s': frame['time_s'],
                             'value': {'frame': native_frame, **actor_packets}})
        original_observations = {
            'frame': native_frame, 'time_s': frame['time_s'],
            'participants': list(actor_packets.values()),
            'world_settings': {'no_rendering_mode': False},
            'rgb_sensors': {'overview': {'frame': native_frame}}}
        evidence.append({'original_frame': native_frame, 'replay_frame': native_frame,
                         'actor_id': 107, 'recording_time_s': frame['time_s'],
                         'replay_simulation_time_s': frame['time_s'],
                         'ego': {'position_m': point['position_m'], 'heading_deg': 0,
                                 'speed_mps': subject_speed,
                                 'speed_provenance': 'original_trace_actor_get_velocity',
                                 'body_vertices_m': body},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -1, 's_m': centre[0] + 100}},
                         'original_observations': original_observations})
        graph.graph['frame'] = native_frame
        graph.graph['observed_evidence'] = original_observations
        name = f'{native_frame:08d}.pkl'
        (graph_dir / name).write_bytes(pickle.dumps(graph, protocol=4))
        frames.append({'frame': native_frame, 'time_s': frame['time_s'],
                       'simulation_time': frame['time_s'],
                       'base': 'graphs/base/' + name})
    _write_rows(source / 'trace.jsonl', trace)
    _write_rows(source / 'synchronized_motion_records.jsonl', participants)
    _write_rows(source / 'capture/evidence.jsonl', evidence)
    _write_rows(source / 'capture/native/frames.jsonl', frames)
    (source / 'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    (source / 'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': 480,
        'acquisition': 'original_live_run', 'observation_contract_version': 2,
        'required_observations': ['rel.same_direction', 'rel.surface_gap',
                                  'kin.position', 'rel.occupies'],
        'sources': {'road.xodr': _sha(source / 'road.xodr'),
                    'trace.jsonl': _sha(source / 'trace.jsonl')},
        'synthetic_diagnostic': True}) + '\n')
    (source / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_local_diagnostic',
        'diagnostic_fixture': True, 'native_executed': False}) + '\n')
    compose_four_views({name: source / (camera + '.mkv') for name, camera in (
        ('overview', 'overview'), ('approach', 'front_lamp'),
        ('reference_corner', 'rear_approach'),
        ('driver_reference', 'subject_reference'))},
        source / 'video_frames.jsonl', source / 'raw.mkv')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('witness_1', 'witness_2'), default='witness_1')
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'),
                        default='primary')
    parser.add_argument('--reuse-fixture', type=Path,
                        help='Reuse an already built synthetic fixture from this diagnostic')
    args = parser.parse_args()
    ffmpeg = ROOT / '.runtime-work/linux_arm64/ffmpeg'
    tools = ffmpeg.parent
    if not ffmpeg.is_file() or not (tools / 'ffprobe').is_file():
        raise ValueError('Pinned local FFmpeg tools absent')
    os.environ['PATH'] = str(tools) + os.pathsep + os.environ.get('PATH', '')
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c405647-exact-'))
    source = args.reuse_fixture.resolve() if args.reuse_fixture else scratch / 'fixture'
    print('scratch', scratch, flush=True)
    if args.reuse_fixture:
        if not source.is_dir() or not (source / 'capture/manifest.json').is_file():
            raise ValueError('Reused fixture is incomplete')
    else:
        build(source, args.case, ffmpeg)
    case_id = HERE.name + '__' + args.case
    output = scratch / 'output'
    receipt = run(HERE / 'draft-execution-manifest.json', case_id, source, output,
                  ROOT / 'runtime/pipeline/library',
                  ROOT / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',
                  args.candidate)
    negative = scratch / 'negative'
    materialize_case(HERE / 'draft-execution-manifest.json', case_id,
                     negative, source, args.candidate)
    (negative / 'source-scope.json').unlink()
    failure = subprocess.run([sys.executable, str(negative / 'finalize.py'),
                              '--attempt', str(negative), '--output',
                              str(negative / 'analysis-report.json')],
                             cwd=negative, env=execution_env(), text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             timeout=300)
    if failure.returncode == 0 or 'Missing required source: source-scope.json' not in failure.stdout:
        raise ValueError('Exact missing-source negative did not reject')
    print(json.dumps({'case_id': case_id, 'candidate_id': args.candidate,
                      'positive': {k: v for k, v in receipt.items() if k != 'fixture_manifest'},
                      'negative': {'removed': 'source-scope.json',
                                   'exit_code': failure.returncode},
                      'scope': 'unselected exact synthetic portable diagnostic; no accepted Native recording'}))


if __name__ == '__main__':
    main()
