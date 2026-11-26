"""Generate source-shaped text and black video specifications for CPU checks only."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from geometry import open_drive


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def build(suffix, speed):
    case = HERE.name + '__' + suffix
    source_dir = HERE / 'diagnostic' / suffix
    source_dir.mkdir(parents=True, exist_ok=True)
    context = {'bridge_x_m': [0.0, 100.0], 'sign_limit_mph': 25.0,
               'posting_distance_m': 30.48,
               'native_bridge_survey': [{'requested_x_m': x, 'native_xyz_m': [x, -1.75, z],
                                        'road_id': 1, 'lane_id': -1}
                                        for x, z in [(-75, 0), (0, 8), (50, 8), (100, 8), (175, 0)]],
               'native_sign_survey': [{'id': '101', 's': '69.52', 'orientation': '+',
                                       'value': '25', 'unit': 'mph'},
                                      {'id': '102', 's': '230.48', 'orientation': '-',
                                       'value': '25', 'unit': 'mph'}],
               'department_determination_verified': False,
               'physical_sign_pixels_verified': False,
               'synthetic_diagnostic': True}
    context_file = source_dir / 'bridge-context.json'
    context_file.write_text(json.dumps(context, separators=(',', ':')) + '\n')
    road = open_drive()
    history, trace, frames, evidence, native_frames, graphs = [], [], [], [], [], []
    names = ('overview', 'approach', 'reference_corner', 'driver_reference')
    for i in range(600):
        time = i / 20
        x = -70 + speed * time
        z = 8 if 0 <= x <= 100 else 0
        location = [x, -1.75, z]
        body = [[x+dx, -1.75+dy, z+dz]
                for dx in (-2, 2) for dy in (-.9, .9) for dz in (0, 1.5)]
        history.append({'video_frame': i, 'native_frame': i, 'time_s': time,
                        'subject_id': 10, 'blueprint_id': 'vehicle.audi.tt',
                        'position_xyz_m': location, 'velocity_xyz_mps': [speed, 0, 0],
                        'requested_speed_mps': speed, 'source_kind': 'synthetic_native_sample'})
        trace.append({'frame': i, 'time_s': time,
                      'position': {'x': x, 'y': -1.75, 'z': z},
                      'position_m': location, 'heading_deg': 0, 'speed_mps': speed,
                      'speed_mph': speed / .44704,
                      'velocity_mps': [speed, 0, 0],
                      'control': {'throttle': 0, 'brake': 0, 'hand_brake': False}})
        frames.append({'video_frame': i, 'carla_frame': i, 'native_frame': i,
                       'time_s': time, 'camera_native_frames': {name: i for name in names}})
        evidence.append({'actor_id': 10, 'ego': {'body_vertices_m': body,
                         'heading_deg': 0, 'position_m': location, 'speed_mps': speed,
                         'speed_provenance': 'synthetic_native_sample',
                         'synthetic_diagnostic': True},
                         'original_frame': i, 'other_actors': [],
                         'recording_time_s': time, 'replay_frame': i,
                         'replay_simulation_time_s': time,
                         'world': {'road_projection': {'road_id': 1, 'lane_id': -1,
                                                       'section_id': 0, 's_m': x+100},
                                   'weather': {'cloudiness': 0, 'fog_density': 0,
                                               'precipitation': 0, 'wetness': 0}}})
        graph_path = f'capture/native/graphs/base/{i:08d}.adapter.json'
        native_frames.append({'adapter_graph': f'graphs/base/{i:08d}.adapter.json',
                              'base': f'graphs/base/{i:08d}.adapter.json',
                              'edges': 0, 'frame': i, 'nodes': 1,
                              'simulation_time': time})
        graphs.append({'path': graph_path,
                       'attributes': {'frame': i, 'simulation_time_s': time,
                                      'source': 'C32014 synthetic bridge CPU diagnostic',
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {'entity_id': 10,
                                  'forward': [1.0, 0.0, 0.0], 'sem_class': 'ego',
                                  'threedbbox': body, 'vertex': location}}],
                       'edges': []})
    trace_text = encoded(trace)
    road_sha = hashlib.sha256(road.encode()).hexdigest()
    trace_sha = hashlib.sha256(trace_text.encode()).hexdigest()
    capture_manifest = {'extraction_confirmed': True, 'frames': 600,
                        'sources': {'road.xodr': road_sha, 'trace.jsonl': trace_sha},
                        'synthetic_diagnostic': True}
    files = {'road.xodr': road, 'bridge-speed-history.jsonl': encoded(history),
             'video_frames.jsonl': encoded(frames), 'trace.jsonl': trace_text,
             'capture/evidence.jsonl': encoded(evidence),
             'capture/manifest.json': json.dumps(capture_manifest) + '\n',
             'capture/native/frames.jsonl': encoded(native_frames),
             'capture/recorder_info.txt': 'Synthetic bridge CPU diagnostic; no Native recording or Department evidence.\nCreate 10: vehicle.audi.tt (0)\n'}
    videos = [{'path': name+'.mkv', 'frames': 600, 'width': 1920 if name == 'overview' else 1280,
               'height': 1080 if name == 'overview' else 720, 'fps': 20, 'color': 'black'} for name in names]
    spec_file = source_dir / 'fixture-spec.json'
    spec_file.write_text(json.dumps({'files': files, 'graphs': graphs, 'videos': videos},
                                    separators=(',', ':')) + '\n')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'bridge-context.json',
                           'source': str(context_file.relative_to(ROOT)),
                           'sha256': sha(context_file)}],
              'generator': {'source': str(spec_file.relative_to(ROOT)),
                            'sha256': sha(spec_file)}}
    (source_dir / 'fixture-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    if spec_file.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Fixture specification exceeds returned file limit')
    return {'case_id': case, 'fixture_spec_sha256': sha(spec_file),
            'spec_size': spec_file.stat().st_size}


if __name__ == '__main__':
    print(json.dumps([build('probe_01', 9.0), build('probe_02', 13.0)]))
