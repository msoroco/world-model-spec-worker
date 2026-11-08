"""Exact C422978 synthetic Core/Lean/video package probe; no physical claim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pickle
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from traffic_spec_adapter.adapter import load_graph
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.media import compose_four_views
from worker_exchange.runtime_cli import execution_env

MANIFEST = HERE / 'draft-execution-manifest.json'
VIDEOS = ('overview', 'front', 'sidewalk', 'rear')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))


def make_media(source):
    ffmpeg = ROOT / '.runtime-work/linux_arm64/ffmpeg'
    if not ffmpeg.is_file():
        raise ValueError('Pinned FFmpeg absent')
    for name, size, color in (('overview', '1920x1080', 'blue'),
                              ('front', '1280x720', 'red'),
                              ('sidewalk', '1280x720', 'green'),
                              ('rear', '1280x720', 'yellow')):
        subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error',
                        '-f', 'lavfi', '-i', f'color=c={color}:s={size}:r=20:d=24',
                        '-c:v', 'ffv1', str(source / (name + '.mkv'))],
                       check=True, timeout=180)
    compose_four_views({'overview': source / 'overview.mkv',
                        'approach': source / 'front.mkv',
                        'reference_corner': source / 'sidewalk.mkv',
                        'driver_reference': source / 'rear.mkv'},
                       source / 'video_frames.jsonl', source / 'raw.mkv')


def build(source, case, candidate, media=None):
    source.mkdir()
    saved = HERE / 'native/saved-fixtures' / case / candidate
    shutil.copyfile(saved / 'native-observed.jsonl', source / 'native-observed.jsonl')
    shutil.copyfile(saved / 'native-map-readback.json', source / 'native-map-readback.json')
    shutil.copyfile(HERE / 'native/context-fixtures' / case / candidate / 'city-context.json',
                    source / 'city-context.json')
    shutil.copyfile(saved / 'video_frames.jsonl', source / 'video_frames.jsonl')
    shutil.copyfile(HERE / 'native/road.xodr', source / 'road.xodr')
    observed = rows(source / 'native-observed.jsonl')
    mapping = rows(source / 'video_frames.jsonl')
    trace, evidence, frames = [], [], []
    graph_source = ROOT / 'runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl'
    graph = load_graph(graph_source)
    graph_dir = source / 'capture/native/graphs/base'
    graph_dir.mkdir(parents=True)
    for actor, video in zip(observed, mapping):
        frame, time = actor['native_frame'], actor['time_s']
        center, body = actor['center_native_xy_m'], actor['body_native_xy_m']
        body3 = [[p[0], p[1], z] for p in body for z in (0, 1.5)]
        subject = {'actor_id': 107, 'blueprint': actor['motorcycle_blueprint'],
                   'body_vertices_m': body3, 'heading_deg': 0.0,
                   'velocity_mps': [actor['speed_mps'], 0, 0],
                   'speed_mps': actor['speed_mps'], 'accel_longitudinal_mps2': 0.0}
        original = {'frame': frame, 'time_s': time, 'participants': [subject],
                    'world_settings': {'no_rendering_mode': False},
                    'rgb_sensors': {'overview': {'frame': frame}}}
        trace.append({'frame': frame, 'time_s': time,
                      'position': {'x': center[0], 'y': center[1], 'z': .5},
                      'position_m': [*center, .5], 'heading_deg': 0,
                      'speed_mps': actor['speed_mps'],
                      'speed_mph': actor['speed_mps'] / .44704,
                      'velocity_mps': subject['velocity_mps'],
                      'control': {'throttle': .3, 'brake': 0.0, 'hand_brake': False}})
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 107, 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'position_m': [*center, .5], 'heading_deg': 0,
                                 'speed_mps': actor['speed_mps'],
                                 'speed_provenance': 'original_trace_actor_get_velocity',
                                 'body_vertices_m': body3},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': actor['native_lane_id'],
                                                       's_m': center[0]}},
                         'original_observations': original})
        graph.graph['frame'] = frame
        graph.graph['observed_evidence'] = original
        name = f'{frame:08d}.pkl'
        (graph_dir / name).write_bytes(pickle.dumps(graph, protocol=4))
        frames.append({'frame': frame, 'time_s': time, 'simulation_time': time,
                       'base': 'graphs/base/' + name})
    write_rows(source / 'trace.jsonl', trace)
    write_rows(source / 'capture/evidence.jsonl', evidence)
    write_rows(source / 'capture/native/frames.jsonl', frames)
    (source / 'capture/recorder_info.txt').write_text('Create 107: vehicle.kawasaki.ninja\n')
    (source / 'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': 480,
        'acquisition': 'original_live_run', 'observation_contract_version': 2,
        'required_observations': ['kin.velocity', 'rel.occupies'],
        'sources': {'road.xodr': sha(source / 'road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')},
        'synthetic_diagnostic': True}) + '\n')
    (source / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_local_diagnostic',
        'diagnostic_fixture': True, 'native_executed': False}) + '\n')
    if media:
        for name in (*VIDEOS, 'raw'):
            shutil.copyfile(media / (name + '.mkv'), source / (name + '.mkv'))
    else:
        make_media(source)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('witness_1', 'witness_2'), default='witness_1')
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'), default='primary')
    parser.add_argument('--media-source', type=Path)
    args = parser.parse_args()
    os.environ['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + os.environ.get('PATH', '')
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c422978-full-'))
    source = scratch / 'source'
    build(source, args.case, args.candidate, args.media_source)
    print('scratch', scratch, flush=True)
    result = run(MANIFEST, HERE.name + '__' + args.case, source, scratch / 'output',
                 ROOT / 'runtime/pipeline/library',
                 ROOT / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',
                 args.candidate)
    negative = scratch / 'negative'
    materialize_case(MANIFEST, HERE.name + '__' + args.case, negative, source, args.candidate)
    (negative / 'native-observed.jsonl').unlink()
    failure = subprocess.run([sys.executable, str(negative / 'finalize.py'), '--attempt',
                              str(negative), '--output', str(negative / 'analysis-report.json')],
                             cwd=negative, env=execution_env(), text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    expected = 'Missing required source: native-observed.jsonl'
    if failure.returncode == 0 or expected not in failure.stdout:
        raise ValueError('Missing source negative did not reject')
    folder = HERE / 'draft-candidates' / args.case / args.candidate
    shutil.copyfile(scratch / 'output/compatibility.json', folder / 'full-compatibility.json')
    shutil.copyfile(scratch / 'output/final-decode.json', folder / 'full-final-decode.json')
    (folder / 'full-negative.log').write_text(failure.stdout)
    summary = {'case_id': result['case_id'], 'candidate_id': args.candidate,
               'construction_sha256': result['construction_sha256'],
               'compatibility_sha256': sha(folder / 'full-compatibility.json'),
               'final_decode_sha256': sha(folder / 'full-final-decode.json'),
               'negative_log_sha256': sha(folder / 'full-negative.log'),
               'negative_error': expected, 'positive_checks': result['checks'],
               'scope': 'unselected exact synthetic package; no original Native or accepted delivery'}
    (folder / 'full-package-proof.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
