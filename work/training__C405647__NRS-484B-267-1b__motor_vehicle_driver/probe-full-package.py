"""Probe full Core/video compatibility for one exact unselected 1(b) bundle."""
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

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
sys.path.insert(0, str(FOLDER / 'native'))
from traffic_spec_adapter.adapter import load_graph
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.media import compose_four_views
from worker_exchange.runtime_cli import execution_env
from prove_saved import packet, save

MANIFEST = FOLDER / 'draft-execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value, sort_keys=True) + '\n' for value in values))


def build(source, case, candidate, media_source=None):
    source.mkdir()
    scope, actors = packet(case, candidate)
    save(source, scope, actors)
    mapping, trace, evidence, frames, participants = [], [], [], [], []
    graph_source = ROOT / 'runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl'
    graph = load_graph(graph_source)
    if 'observed_actor_108' in graph:
        graph.remove_node('observed_actor_108')
    graph_dir = source / 'capture/native/graphs/base'
    graph_dir.mkdir(parents=True)
    for index, actor in enumerate(actors):
        native_frame, time = actor['native_frame'], actor['time_s']
        subject = actor['subject']
        approach = actor['approach']
        subject_center = [subject['center_xy_m'][0], -subject['center_xy_m'][1]]
        approach_center = [approach['center_xy_m'][0], -approach['center_xy_m'][1]]
        native_body = [[p[0], -p[1], z] for p in subject['body_xy_m'] for z in (0, 1.5)]
        approach_body = [[approach_center[0] + dx, approach_center[1] + dy, z]
                         for dx in (-2.25, 2.25) for dy in (-.9, .9) for z in (0, 1.5)]
        velocities = {'subject': [subject['speed_mps'], 0, 0], 'approach': [8.0, 0, 0]}
        actor_packets = {}
        for role, aid, body in (('subject', 107, native_body), ('approach', 108, approach_body)):
            actor_packets[role] = {'actor_id': aid, 'blueprint': 'vehicle.lincoln.mkz_2020',
                                   'body_vertices_m': body, 'heading_deg': 0.0,
                                   'velocity_mps': velocities[role],
                                   'speed_mps': velocities[role][0],
                                   'accel_longitudinal_mps2': 0.0}
        original = {'frame': native_frame, 'time_s': time,
                    'participants': list(actor_packets.values()),
                    'world_settings': {'no_rendering_mode': False},
                    'rgb_sensors': {'overview': {'frame': native_frame}}}
        point = {'frame': native_frame, 'time_s': time,
                 'position': {'x': subject_center[0], 'y': subject_center[1], 'z': .5},
                 'position_m': [*subject_center, .5], 'heading_deg': 0,
                 'speed_mps': subject['speed_mps'],
                 'speed_mph': subject['speed_mps'] / .44704,
                 'velocity_mps': velocities['subject'],
                 'control': {'throttle': .3, 'brake': 0.0, 'hand_brake': False}}
        trace.append(point)
        mapping.append({'video_frame': index, 'carla_frame': native_frame,
                        'native_frame': native_frame, 'time_s': time})
        participants.append({'time_s': time, 'value': {'frame': native_frame, **actor_packets}})
        evidence.append({'original_frame': native_frame, 'replay_frame': native_frame,
                         'actor_id': 107, 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'position_m': point['position_m'], 'heading_deg': 0,
                                 'speed_mps': subject['speed_mps'],
                                 'speed_provenance': 'original_trace_actor_get_velocity',
                                 'body_vertices_m': native_body},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1, 'section_id': 0,
                                                       'lane_id': -1, 's_m': subject_center[0] + 40}},
                         'original_observations': original})
        graph.graph['frame'] = native_frame
        graph.graph['observed_evidence'] = original
        name = f'{native_frame:08d}.pkl'
        (graph_dir / name).write_bytes(pickle.dumps(graph, protocol=4))
        frames.append({'frame': native_frame, 'time_s': time,
                       'simulation_time': time, 'base': 'graphs/base/' + name})
    write_rows(source / 'trace.jsonl', trace)
    write_rows(source / 'video_frames.jsonl', mapping)
    write_rows(source / 'synchronized_motion_records.jsonl', participants)
    write_rows(source / 'capture/evidence.jsonl', evidence)
    write_rows(source / 'capture/native/frames.jsonl', frames)
    (source / 'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    (source / 'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': 480,
        'acquisition': 'original_live_run', 'observation_contract_version': 2,
        'required_observations': ['rel.same_direction', 'rel.surface_gap',
                                  'kin.position', 'rel.occupies'],
        'sources': {'road.xodr': sha(FOLDER / 'native/drafts/road.xodr'),
                    'trace.jsonl': sha(source / 'trace.jsonl')},
        'synthetic_diagnostic': True}) + '\n')
    (source / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_local_diagnostic',
        'diagnostic_fixture': True, 'native_executed': False}) + '\n')
    if media_source:
        for name in ('overview', 'front_lamp', 'right_edge', 'rear_approach', 'raw'):
            shutil.copyfile(media_source / (name + '.mkv'), source / (name + '.mkv'))
    else:
        ffmpeg = ROOT / '.runtime-work/linux_arm64/ffmpeg'
        if not ffmpeg.is_file():
            raise ValueError('Pinned local FFmpeg absent')
        for name, size, color in (('overview', '1920x1080', 'blue'),
                                  ('front_lamp', '1280x720', 'red'),
                                  ('right_edge', '1280x720', 'green'),
                                  ('rear_approach', '1280x720', 'yellow')):
            subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', f'color=c={color}:s={size}:r=20:d=24',
                            '-c:v', 'ffv1', str(source / (name + '.mkv'))],
                           check=True, timeout=180)
        compose_four_views({'overview': source / 'overview.mkv',
                            'approach': source / 'front_lamp.mkv',
                            'reference_corner': source / 'right_edge.mkv',
                            'driver_reference': source / 'rear_approach.mkv'},
                           source / 'video_frames.jsonl', source / 'raw.mkv')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('reference', 'contrast'), default='reference')
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'), default='primary')
    parser.add_argument('--reuse-source', type=Path)
    parser.add_argument('--media-source', type=Path)
    args = parser.parse_args()
    tools = ROOT / '.runtime-work/linux_arm64'
    os.environ['PATH'] = str(tools) + os.pathsep + os.environ.get('PATH', '')
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c405647-1b-full-'))
    source = args.reuse_source.resolve() if args.reuse_source else scratch / 'source'
    print('scratch', scratch, flush=True)
    if args.reuse_source:
        if not (source / 'capture/manifest.json').is_file():
            raise ValueError('Reused synthetic capture is incomplete')
    else:
        build(source, args.case, args.candidate,
              args.media_source.resolve() if args.media_source else None)
    result = run(MANIFEST, FOLDER.name + '__' + args.case, source, scratch / 'output',
                 ROOT / 'runtime/pipeline/library',
                 ROOT / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',
                 args.candidate)
    negative = scratch / 'negative'
    materialize_case(MANIFEST, FOLDER.name + '__' + args.case,
                     negative, source, args.candidate)
    (negative / 'source-scope.json').unlink()
    failure = subprocess.run([sys.executable, str(negative / 'finalize.py'),
                              '--attempt', str(negative), '--output',
                              str(negative / 'analysis-report.json')],
                             cwd=negative, env=execution_env(), text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             timeout=120)
    expected = 'Missing required source: source-scope.json'
    if failure.returncode == 0 or expected not in failure.stdout:
        raise ValueError('Exact missing-source negative did not reject')
    folder = FOLDER / 'draft-candidates' / args.case / args.candidate
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
