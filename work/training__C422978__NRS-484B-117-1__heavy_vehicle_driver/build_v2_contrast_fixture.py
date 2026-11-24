"""Build source-hashed 600-frame diagnostic inputs for the current runtime."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE/'native/saved-fixtures/contrast/primary'
OUT = HERE/'v2-contrast-primary-fixture'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True)+'\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def write_rows(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(item, sort_keys=True)+'\n' for item in records))


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    observed = rows(SOURCE/'native-observed.jsonl')
    mapping = rows(SOURCE/'video_frames.jsonl')
    assert len(observed) == len(mapping) == 600
    trace, evidence, graphs, native_frames = [], [], [], []
    for item, frame in zip(observed, mapping):
        native = item['native_frame']
        x, y = item['center_native_xy_m']
        t = item['time_s']
        speed = item['speed_mps']
        body = item['body_native_xy_m']
        vertices = [[px, py, z] for px, py in body for z in (0.0, 1.5)]
        trace.append({'frame': native, 'time_s': t,
                      'position': {'x': x, 'y': y, 'z': 0.5},
                      'position_m': [x, y, 0.5], 'heading_deg': 0,
                      'speed_mps': speed, 'speed_mph': speed*2.2369362920544,
                      'control': {'throttle': 0, 'brake': 0, 'hand_brake': False}})
        evidence.append({'original_frame': native, 'recording_time_s': t,
                         'ego': {'body_vertices_m': vertices,
                                 'position_m': [x, y, 0.5], 'heading_deg': 0,
                                 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'synthetic_diagnostic': True},
                         'replay_frame': native, 'replay_simulation_time_s': t,
                         'actor_id': 107,
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 1,
                                                       'section_id': 0,
                                                       'lane_id': item['native_lane_id'],
                                                       's_m': x}}})
        relative = f'graphs/base/{native:08d}.adapter.json'
        native_frames.append({'frame': native, 'simulation_time': t,
                              'adapter_graph': relative, 'base': relative,
                              'nodes': 1, 'edges': 0})
        graphs.append({'path': 'capture/native/'+relative,
                       'attributes': {'frame': native, 'simulation_time_s': t,
                                      'synthetic_diagnostic': True,
                                      'source': 'C422978 heavy-vehicle diagnostic'},
                       'nodes': [{'id': 'ego', 'attributes': {
                           'sem_class': 'ego', 'entity_id': 107,
                           'vertex': [x, y, 0.5], 'forward': [1.0, 0.0, 0.0],
                           'threedbbox': vertices}}], 'edges': []})
    write_rows(OUT/'trace.jsonl', trace)
    write_rows(OUT/'video_frames.jsonl', mapping)
    write_rows(OUT/'capture/evidence.jsonl', evidence)
    shutil.copyfile(HERE/'native/road.xodr', OUT/'road.xodr')
    shutil.copyfile(SOURCE/'native-observed.jsonl', OUT/'native-observed.jsonl')
    shutil.copyfile(SOURCE/'native-map-readback.json', OUT/'native-map-readback.json')
    shutil.copyfile(SOURCE/'native-capture-report.json', OUT/'native-capture-report.json')
    write(OUT/'capture/manifest.json', {
        'extraction_confirmed': True, 'frames': 600,
        'synthetic_diagnostic': True,
        'sources': {'road.xodr': sha(OUT/'road.xodr'),
                    'trace.jsonl': sha(OUT/'trace.jsonl')}})
    specification = {'files': {'capture/native/frames.jsonl': ''.join(
        json.dumps(row, separators=(',', ':'))+'\n' for row in native_frames),
        'capture/recorder_info.txt': 'synthetic CPU diagnostic; no CARLA recorder\nCreate 107: vehicle.carlamotors.carlacola (0)\n'},
        'graphs': graphs,
        'videos': [{'path': name+'.mkv', 'frames': 600,
                    'width': 1920 if name == 'overview' else 1280,
                    'height': 1080 if name == 'overview' else 720,
                    'fps': 20, 'color': 'black'}
                   for name in ('overview', 'approach',
                                'reference_corner', 'driver_reference')]}
    spec_path = HERE/'v2-contrast-primary-fixture-spec.json'
    write(spec_path, specification)
    sources = []
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and path.name != 'road.xodr':
            sources.append({'path': str(path.relative_to(OUT)),
                            'source': str(path.relative_to(ROOT)),
                            'sha256': sha(path)})
    recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
              'generator': {'source': str(spec_path.relative_to(ROOT)),
                            'sha256': sha(spec_path)}}
    recipe_path = HERE/'v2-contrast-primary-fixture-recipe.json'
    write(recipe_path, recipe)
    return {'source_count': len(sources), 'graph_count': len(graphs),
            'video_count': len(specification['videos']),
            'recipe_sha256': sha(recipe_path)}


if __name__ == '__main__':
    print(json.dumps(build()))
