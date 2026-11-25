"""Build explicit synthetic sources for software compatibility, never site evidence."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / 'tests'))
from test_saved_backing import fixture, write


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value, *, compact=False):
    path.write_text(json.dumps(value, allow_nan=False,
                               separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n', encoding='utf-8')


def build():
    video_root = REPO / '.runtime-work/c111301-nov25/fixture-videos'
    dimensions = {'overview': (1920, 1080), 'approach': (1280, 720),
                  'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
    source = HERE / 'diagnostic-fixture-source.json'
    dump(source, {'format': 'worker-diagnostic-source', 'scope': 'synthetic software fixture only',
                  'original_site_evidence': False, 'physical_acceptance_claimed': False})
    for suffix in ('pedestrian_yield', 'pedestrian_continue'):
        case = HERE.name + '__' + suffix
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work', prefix='c111301-fixture-build-') as tmp:
            root = Path(tmp)
            receipt = fixture(root, case)
            frames = json.loads((root / 'telemetry.json').read_text())
            if suffix == 'pedestrian_continue':
                for row in frames:
                    row['brake'] = 0.0
                    row['vehicle_velocity_xy'] = [-0.5, 0.0]
                receipt['telemetry'] = write(root, 'telemetry.json', frames)
            trace = root / 'trace.jsonl'
            trace.write_text(''.join(json.dumps({
                'frame': i, 'time_s': row['time_s'],
                'position': {'x': row['vehicle_xy'][0], 'y': row['vehicle_xy'][1], 'z': 0.0},
                'position_m': [*row['vehicle_xy'], 0.0], 'heading_deg': 0.0,
                'speed_mps': abs(row['vehicle_velocity_xy'][0]),
                'speed_mph': abs(row['vehicle_velocity_xy'][0]) / 0.44704,
                'velocity_mps': [*row['vehicle_velocity_xy'], 0.0],
                'control': {'brake': row['brake'], 'throttle': 0.0,
                            'steer': 0.0, 'reverse': row['reverse_gear']}}) + '\n'
                for i, row in enumerate(frames)), encoding='utf-8')
            receipt['trace'] = {'path': 'trace.jsonl', 'sha256': sha(trace)}
            receipt['source_kind'] = 'synthetic_fixture'
            receipt['diagnostic'] = True
            receipt['source_id'] = 'diagnostic:' + suffix
            receipt['media'] = {name: {'path': name + '.mkv',
                                       'sha256': sha(video_root / (name + '.mkv'))}
                                for name in dimensions}
            dump(root / 'acquisition.json', receipt)
            dump(root / 'diagnostic-fixture.json',
                 {'format': 'worker-diagnostic-fixture', 'diagnostic_fixture': True})
            dump(root / 'acquisition-provenance.json',
                 {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True})
            capture = root / 'capture'
            native = capture / 'native'
            native.mkdir(parents=True)
            evidence = capture / 'evidence.jsonl'
            evidence.write_text(''.join(json.dumps({
                'original_frame': i, 'replay_frame': i, 'actor_id': 7,
                'recording_time_s': row['time_s'],
                'replay_simulation_time_s': row['time_s'],
                'ego': {'position_m': [*row['vehicle_xy'], 0.0],
                        'heading_deg': 0.0,
                        'speed_mps': abs(row['vehicle_velocity_xy'][0]),
                        'body_vertices_m': [
                            [row['vehicle_xy'][0] + dx,
                             row['vehicle_xy'][1] + dy, 0.0]
                            for dx in (-1.0, 1.0) for dy in (-0.9, 0.9)],
                        'speed_provenance': 'synthetic_native_sample'},
                'world': {'weather': {}, 'road_projection': {}},
                'original_observations': {'frame': i, 'time_s': row['time_s'],
                                          'rgb_sensors': [{'actor_id': 100, 'blueprint': 'sensor.camera.rgb'}],
                                          'world_settings': {'no_rendering_mode': False},
                                          'devices': [], 'participants': [], 'relations': []},
                'timing': {}, 'visibility': None}) + '\n'
                for i, row in enumerate(frames)), encoding='utf-8')
            native_frames = native / 'frames.jsonl'
            native_frames.write_text(''.join(json.dumps({
                'frame': i, 'simulation_time': row['time_s'],
                'abstract': None, 'base': None, 'nodes': 0, 'edges': 0,
                'extraction_seconds': 0, 'capture_seconds': 0,
                'adapter_graph': 'graphs/base/' + f'{i:08d}.adapter.json'}) + '\n'
                for i, row in enumerate(frames)), encoding='utf-8')
            (capture / 'recorder_info.txt').write_text(
                'Version: 1\nMap: OriginalTown\n Create 7: vehicle.audi.a2 (0) at (0, 0, 0)\n',
                encoding='utf-8')
            dump(capture / 'manifest.json', {
                'acquisition': 'diagnostic_fixture', 'case_id': case,
                'complete_driving_lanes': False, 'extraction_confirmed': True,
                'frames': 900, 'map': 'OriginalTown',
                'observation_contract_version': 2, 'required_observations': [],
                'source_run': 'diagnostic:c111301',
                'sources': {'road.xodr': sha(root / 'road.xodr'),
                            'trace.jsonl': sha(trace)}, 'status': 'draft'})
            files = {str(p.relative_to(root)): p.read_text(encoding='utf-8')
                     for p in root.rglob('*') if p.is_file() and p.suffix != '.mkv'}
            graphs = []
            for i, row in enumerate(frames):
                observation = {
                    'frame': i, 'time_s': row['time_s'],
                    'rgb_sensors': [{'actor_id': 100, 'blueprint': 'sensor.camera.rgb'}],
                    'world_settings': {'no_rendering_mode': False},
                    'devices': [], 'participants': [], 'relations': []}
                graphs.append({'path': 'capture/native/graphs/base/' + f'{i:08d}.adapter.json',
                               'attributes': {'frame': i, 'simulation_time_s': row['time_s'],
                                              'observed_evidence': observation,
                                              'units': {'carla_speed': 'm/s', 'position': 'm'}},
                               'nodes': [{'id': 'ego', 'attributes': {
                                   'entity_id': 7, 'forward': [1, 0, 0],
                                   'sem_class': 'ego', 'vertex': [*row['vehicle_xy'], 0.0]}}],
                               'edges': []})
            videos = [{'path': name + '.mkv', 'frames': 900, 'width': width,
                       'height': height, 'fps': 20, 'color': 'black'}
                      for name, (width, height) in dimensions.items()]
            spec = HERE / ('diagnostic-' + suffix + '-spec.json')
            dump(spec, {'files': files, 'graphs': graphs, 'videos': videos}, compact=True)
            recipe = HERE / ('diagnostic-' + suffix + '-recipe.json')
            dump(recipe, {'format': 'worker-fixture-recipe',
                          'sources': [{'path': source.name,
                                       'source': str(source.relative_to(REPO)),
                                       'sha256': sha(source)}],
                          'generator': {'source': str(spec.relative_to(REPO)),
                                        'sha256': sha(spec)}})
            print(suffix, 'source files', len(files), 'spec bytes', spec.stat().st_size)


if __name__ == '__main__':
    build()
