"""Positive and removed-source synthetic saved-processing proof for both cases."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / 'native'
OUT = ROOT / '.runtime-work/c111294-saved-fixtures'
sys.path.insert(0, str(NATIVE))
from measure import synthetic
sys.path.insert(0, str(ROOT / 'runtime/pipeline'))
from scenario_pipeline.worker_exchange.measurement_contract import verify_report


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def make(root, suffix, full_resolution=False):
    root.mkdir(parents=True)
    (root / 'capture').mkdir()
    config = json.loads(next(item['content'] for item in json.loads(
        (HERE / 'draft-candidates' / suffix / 'primary/construction.json').read_text())['files']
        if item['path'] == 'config.json'))
    (root / 'config.json').write_text(json.dumps(config))
    shutil.copyfile(NATIVE / 'road.xodr', root / 'road.xodr')
    from measure import sha as measure_sha
    interaction = synthetic(suffix, measure_sha(root / 'road.xodr'))
    (root / 'interaction.json').write_text(json.dumps(interaction, sort_keys=True) + '\n')
    frames = interaction['frames']
    trace = []
    evidence = []
    mapping = []
    native = []
    for index, row in enumerate(frames):
        frame = index + 100
        time = (index + 1) / 20
        bicycle = row['bicycle']
        motor = row['motor_vehicle']
        center = bicycle['center_xy_m']
        body = bicycle['body_xy_m']
        vertices = [[x, y, z] for x, y in body for z in (0, 1.5)]
        trace.append({'frame': frame, 'time_s': time,
            'position': {'x': center[0], 'y': center[1], 'z': .5},
            'position_m': center + [.5], 'heading_deg': 90,
            'speed_mps': bicycle['speed_mps'], 'speed_mph': bicycle['speed_mps'] / .44704,
            'control': {'throttle': 0, 'brake': 0, 'hand_brake': False}})
        evidence.append({'original_frame': frame, 'recording_time_s': time,
            'replay_frame': frame, 'replay_simulation_time_s': time, 'actor_id': 101,
            'ego': {'body_vertices_m': vertices, 'position_m': center + [.5],
                    'heading_deg': 90, 'speed_mps': bicycle['speed_mps'],
                    'speed_provenance': 'original_trace_actor_get_velocity'},
            'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                  'wetness': 0, 'fog_density': 0},
                      'road_projection': {'road_id': 13, 'section_id': 0,
                                          'lane_id': -1, 's_m': max(0, center[1] + 25)}}})
        mapping.append({'video_frame': index, 'native_frame': frame,
                        'carla_frame': frame, 'time_s': time})
        native.append({'native_frame': frame, 'time_s': time, 'bicycle': bicycle,
                       'motor_vehicle': motor, 'bicycle_body_vertices_m': vertices,
                       'motor_vehicle_body_vertices_m': [[x,y,z] for x,y in motor['body_xy_m'] for z in (0,1.5)],
                       'synthetic_diagnostic': True})
    for name, rows in (('trace.jsonl', trace), ('capture/evidence.jsonl', evidence),
                       ('video_frames.jsonl', mapping), ('native_samples.jsonl', native)):
        write_rows(root / name, rows)
    (root / 'capture/manifest.json').write_text(json.dumps({'extraction_confirmed': True,
        'frames': 600, 'sources': {'interaction.json': sha(root / 'interaction.json')},
        'synthetic_diagnostic': True}))
    (root / 'capture/recorder_info.txt').write_text('Create 101: vehicle.bh.crossbike\n')
    # Derived channels are intentionally absent. The saved finalizer must build
    # them from retained Native samples and the original frame map.
    ffmpeg = ROOT / '.runtime-work/linux_arm64/ffmpeg'
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        size = '1920x1080' if name == 'overview' and full_resolution else (
            '1280x720' if full_resolution else '32x32')
        subprocess.run([str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'color=c=black:s=' + size + ':r=20:d=30', '-frames:v', '600',
            '-c:v', 'ffv1', str(root / (name + '.mkv'))], check=True, timeout=120)
    x,y,z=20,-24,40
    (root/'camera_context.json').write_text(json.dumps({'name':'overview',
        'width':1920 if full_resolution else 32,'height':1080 if full_resolution else 32,
        'fov_deg':90,'pose':{'xyz_m':[x,y,z],
        'yaw_deg':math.degrees(math.atan2(-y,-x)),
        'pitch_deg':math.degrees(math.atan2(1.0-z,math.hypot(x,y)))},
        'source_kind':'synthetic_cpu_camera_emulation'}))
    if full_resolution:
        folder = root / 'capture/native/graphs/base'
        folder.mkdir(parents=True)
        graph_rows = []
        for item in mapping:
            frame = item['native_frame']
            center = trace[item['video_frame']]['position_m']
            graph_path = folder / f'{frame:08d}.adapter.json'
            graph_path.write_text(json.dumps({
                'format': 'native-adapter-graph-v1', 'multigraph': False,
                'metadata': {'frame': frame, 'simulation_time_s': item['time_s'],
                             'synthetic_diagnostic': True},
                'nodes': [{'id': 'ego', 'attributes': {'sem_class': 'ego',
                    'entity_id': 101, 'vertex': center, 'forward': [0, 1, 0],
                    'threedbbox': evidence[item['video_frame']]['ego']['body_vertices_m']}}],
                'edges': []}, separators=(',', ':')) + '\n')
            graph_rows.append({'frame': frame, 'simulation_time': item['time_s'],
                'time_s': item['time_s'],
                'adapter_graph': f'graphs/base/{frame:08d}.adapter.json',
                'base': f'graphs/base/{frame:08d}.adapter.json',
                'nodes': 1, 'edges': 0, 'synthetic_diagnostic': True})
        write_rows(root / 'capture/native/frames.jsonl', graph_rows)
        manifest = json.loads((root / 'capture/manifest.json').read_text())
        manifest['sources'].update({'road.xodr': sha(root / 'road.xodr'),
                                    'trace.jsonl': sha(root / 'trace.jsonl')})
        (root / 'capture/manifest.json').write_text(json.dumps(manifest))
    manifest=json.loads((root/'capture/manifest.json').read_text())
    for name in ('road.xodr','interaction.json','native_samples.jsonl',
                 'video_frames.jsonl','camera_context.json','overview.mkv'):
        manifest['sources'][name]=sha(root/name)
    (root/'capture/manifest.json').write_text(json.dumps(manifest))


def emulate_original_shape(root):
    """Exercise the original-source parser with explicitly synthetic provenance."""
    from runner_capture import original_row
    source = json.loads((root / 'interaction.json').read_text())
    native = [json.loads(line) for line in (root / 'native_samples.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
    source['source_kind'] = 'synthetic_original_shape_emulation'
    for index, (row, sample, frame) in enumerate(zip(source['frames'], native, mapping)):
        bicycle = {**row['bicycle'], 'blueprint_id': 'vehicle.bh.crossbike'}
        motor = {**row['motor_vehicle'], 'blueprint_id': 'vehicle.lincoln.mkz_2020'}
        source['frames'][index] = original_row(index, frame['native_frame'], bicycle, motor,
            row['motor_vehicle']['brake_applied'])
        sample['bicycle'] = source['frames'][index]['bicycle']
        sample['motor_vehicle'] = source['frames'][index]['motor_vehicle']
    (root / 'interaction.json').write_text(json.dumps(source, sort_keys=True)+'\n')
    write_rows(root / 'native_samples.jsonl', native)
    manifest = json.loads((root / 'capture/manifest.json').read_text())
    manifest['sources']['interaction.json'] = sha(root / 'interaction.json')
    manifest['sources']['native_samples.jsonl'] = sha(root / 'native_samples.jsonl')
    manifest['synthetic_diagnostic'] = True
    (root / 'capture/manifest.json').write_text(json.dumps(manifest))


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PATH'] = str(ROOT / '.runtime-work/linux_arm64') + os.pathsep + env.get('PATH', '')
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'runtime/pipeline'),
        str(ROOT / 'runtime/pipeline/scenario_pipeline'), env.get('PYTHONPATH', '')))
    results = []
    for suffix in ('witness_1', 'witness_2'):
        base = OUT / (suffix + '-base')
        if base.exists(): shutil.rmtree(base)
        make(base, suffix)
        positive = OUT / (suffix + '-positive')
        negative = OUT / (suffix + '-negative')
        for path in (positive, negative):
            if path.exists(): shutil.rmtree(path)
            shutil.copytree(base, path)
        original = {str(p.relative_to(positive)): sha(p) for p in positive.rglob('*') if p.is_file()}
        command = [sys.executable, str(NATIVE / 'finalize.py'), '--attempt', str(positive),
                   '--output', str(positive / 'analysis-report.json')]
        completed = subprocess.run(command, text=True, capture_output=True, env=env, timeout=300)
        if completed.returncode: raise RuntimeError(completed.stdout + completed.stderr)
        if any(sha(positive / name) != value for name, value in original.items()):
            raise RuntimeError('Finalizer changed saved acquisition')
        report = json.loads((positive / 'analysis-report.json').read_text())
        contract = json.loads((NATIVE / ('measurement-contract-' + suffix + '.json')).read_text())
        verify_report(contract, report, positive)
        result = json.loads((positive / 'result.json').read_text())
        assert result['target_checks'][0]['matched'] and not result['accepted']
        (negative / 'interaction.json').unlink()
        rejected = subprocess.run([sys.executable, str(NATIVE / 'finalize.py'), '--attempt',
            str(negative), '--output', str(negative / 'analysis-report.json')],
            text=True, capture_output=True, env=env, timeout=300)
        if rejected.returncode == 0 or 'Missing required source: interaction.json' not in rejected.stderr:
            raise RuntimeError('Missing interaction source accepted: ' + rejected.stdout + rejected.stderr)
        results.append({'case': suffix, 'frames': 600,
            'braking_frames': report['measurements']['bicycle_motorist_interaction']['value']['motor_braking_frames'],
            'positive_result_sha256': sha(positive / 'result.json'),
            'positive_report_sha256': sha(positive / 'analysis-report.json'),
            'missing_source_rejected': True, 'saved_acquisition_unchanged': True,
            'scope': 'synthetic CPU only; original pixels and physical behavior unverified'})
    return results


if __name__ == '__main__':
    print(json.dumps({'passed': True, 'cases': run()}, indent=2))
