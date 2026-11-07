"""Build an exact-case synthetic Core fixture and run the pinned portable path.

This fixture is diagnostic only. Its graph, camera colors and actor packets are
generated on CPU from the authored request, never from a Native recording.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import pickle
import shutil
import subprocess
import sys
import tempfile

import networkx as nx

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.media import compose_four_views
from worker_exchange.package_compatibility import run

FFMPEG = REPO / '.runtime-work/linux_arm64/ffmpeg'
DECODER = REPO / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in values))


def video(path, width, height, color):
    subprocess.run([str(FFMPEG), '-nostdin', '-hide_banner', '-loglevel', 'error',
                    '-f', 'lavfi', '-i', f'color=c={color}:s={width}x{height}:r=20:d=24',
                    '-an', '-c:v', 'ffv1', '-n', str(path)], check=True, timeout=180)


def fixture(destination, case, candidate):
    destination.mkdir()
    source = HERE / 'synthetic-saved' / case / candidate
    native = rows(source / 'native_samples.jsonl')
    mapping = rows(source / 'video_frames.jsonl')
    if len(native) != 480 or len(mapping) != 480:
        raise ValueError('Exact saved 480-frame source required')
    for name in ('native_samples.jsonl', 'video_frames.jsonl'):
        shutil.copy2(source / name, destination / name)
    shutil.copy2(REPO / '.runtime-work/c111331-signal-cpu-video' / case / candidate /
                 'signal_reference.mkv', destination / 'signal_reference.mkv')
    graph_dir = destination / 'capture/native/graphs/base'
    graph_dir.mkdir(parents=True)
    trace, evidence, frames = [], [], []
    speed = 20 * math.dist(native[0]['native_center_xy_m'], native[1]['native_center_xy_m'])
    for index, (sample, join) in enumerate(zip(native, mapping)):
        frame = sample['native_frame']
        if join['carla_frame'] != frame or join['video_frame'] != index:
            raise ValueError('Synthetic Core source frame join differs')
        x, y = sample['native_center_xy_m']
        heading = sample['native_yaw_deg']
        angle = math.radians(heading)
        velocity = [speed * math.cos(angle), speed * math.sin(angle), 0.0]
        vertices = [[point[0], point[1], z]
                    for point in sample['native_body_xy_m'] for z in (0.0, 1.5)]
        point = {'frame': frame, 'time_s': sample['time_s'],
                 'position': {'x': x, 'y': y, 'z': .5},
                 'position_m': [x, y, .5], 'heading_deg': heading,
                 'speed_mps': speed, 'speed_mph': speed / .44704,
                 'velocity_mps': velocity,
                 'control': {'throttle': .3, 'brake': 0.0, 'hand_brake': False}}
        trace.append(point)
        actor = {'actor_id': 107, 'blueprint': 'vehicle.lincoln.mkz_2020',
                 'body_vertices_m': vertices, 'heading_deg': heading,
                 'velocity_mps': velocity, 'speed_mps': speed,
                 'accel_longitudinal_mps2': 0.0}
        observed = {'frame': frame, 'time_s': sample['time_s'],
                    'participants': [actor], 'world_settings': {'no_rendering_mode': False},
                    'rgb_sensors': {'overview': {'frame': frame}}}
        road_id = 1 if y < -7 else 13 if x < 7 else 2
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 107, 'recording_time_s': sample['time_s'],
                         'replay_simulation_time_s': sample['time_s'],
                         'ego': {'position_m': point['position_m'],
                                 'heading_deg': heading, 'speed_mps': speed,
                                 'speed_provenance': 'original_trace_actor_get_velocity',
                                 'body_vertices_m': vertices},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': road_id,
                                                       'section_id': 0, 'lane_id': -1,
                                                       's_m': index * speed / 20}},
                         'original_observations': observed})
        graph = nx.DiGraph()
        graph.graph.update(frame=frame, observed_evidence=observed)
        phase = sample['observed_signal_state'].capitalize()
        graph.add_node('signal_601', sem_class='traffic.traffic_light',
                       carla_id=601, vertex=[3.5, -13.0, 4.0],
                       light_state='TrafficLightState.' + phase,
                       observed_governs=[[1, 0, -1]])
        graph_name = f'{frame:08d}.pkl'
        (graph_dir / graph_name).write_bytes(pickle.dumps(graph, protocol=4))
        frames.append({'frame': frame, 'time_s': sample['time_s'],
                       'simulation_time': sample['time_s'],
                       'base': 'graphs/base/' + graph_name})
    write_rows(destination / 'trace.jsonl', trace)
    write_rows(destination / 'capture/evidence.jsonl', evidence)
    write_rows(destination / 'capture/native/frames.jsonl', frames)
    (destination / 'capture/recorder_info.txt').write_text(
        'Create 107: vehicle.lincoln.mkz_2020\n')
    (destination / 'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': 480,
        'acquisition': 'original_live_run', 'observation_contract_version': 2,
        'required_observations': ['kin.position', 'st.intersection', 'dev.traffic_signal'],
        'sources': {'road.xodr': sha(HERE / 'road.xodr'),
                    'trace.jsonl': sha(destination / 'trace.jsonl')},
        'synthetic_diagnostic': True}, indent=2) + '\n')
    (destination / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_local_diagnostic',
        'diagnostic_fixture': True, 'native_executed': False}) + '\n')
    camera_paths = {}
    for name, width, height, color in (
            ('overview', 1920, 1080, 'blue'),
            ('approach', 1280, 720, 'green'),
            ('reference_corner', 1280, 720, 'yellow'),
            ('driver_reference', 1280, 720, 'red')):
        camera_paths[name] = destination / (name + '.mkv')
        video(camera_paths[name], width, height, color)
    compose_four_views(camera_paths, destination / 'video_frames.jsonl',
                       destination / 'raw.mkv')
    return {'fixture_sha256': sha(destination / 'capture/manifest.json'),
            'frames': 480, 'synthetic_only': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('reference', 'contrast'), required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'),
                        default='primary')
    args = parser.parse_args()
    if not FFMPEG.is_file() or not DECODER.is_file():
        raise ValueError('Pinned local FFmpeg or Lean decoder absent')
    os.environ['PATH'] = str(FFMPEG.parent) + os.pathsep + os.environ.get('PATH', '')
    scratch = Path(tempfile.mkdtemp(dir=REPO / '.runtime-work', prefix='c111331-portable-'))
    print('scratch', scratch, flush=True)
    source = scratch / 'fixture'
    print(json.dumps(fixture(source, args.case, args.candidate), sort_keys=True), flush=True)
    case_id = HERE.parent.name + '__' + args.case
    receipt = run(HERE / 'package-manifest.json', case_id, source, scratch / 'output',
                  REPO / 'runtime/pipeline/library', DECODER, args.candidate)
    print(json.dumps({'passed': receipt['passed'], 'case_id': case_id,
                      'candidate_id': args.candidate, 'scope': receipt['scope']}, sort_keys=True))


if __name__ == '__main__':
    main()
