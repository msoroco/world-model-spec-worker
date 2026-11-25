"""Generate source-hashed 600-frame pedestrian diagnostics for current-v2 CPU proofs."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from prove_saved_source_analysis import sample

VIEWS = (('overview', 1920, 1080, 'blue'),
         ('approach', 1280, 720, 'green'),
         ('reference_corner', 1280, 720, 'white'),
         ('driver_reference', 1280, 720, 'red'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':')) + '\n')


def rows(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(item, separators=(',', ':')) + '\n'
                            for item in data))


def build(suffix):
    folder = HERE / 'selected-v2-source' / suffix
    folder.parent.mkdir(exist_ok=True)
    if folder.exists():
        raise ValueError('Retain selected diagnostic source; use a fresh revision')
    sample(folder, suffix == 'contrast')
    construction = json.loads((HERE / 'selected-candidates' / suffix /
                               'primary/construction.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    write(folder / 'config.json', config)
    write(folder / 'construction.json', construction)
    mapping = [json.loads(line) for line in (folder / 'video_frames.jsonl').read_text().splitlines()]
    evidence = []
    trace = []
    for row in mapping:
        i, frame, time_s = row['video_frame'], row['carla_frame'], row['time_s']
        y = .2 if suffix == 'contrast' and i >= 80 else -.2
        position = [0.0, y, 1.0]
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': 0.0, 'y': y, 'z': 1.0},
                      'position_m': position, 'heading_deg': 90,
                      'speed_mps': 0.0, 'speed_mph': 0.0,
                      'speed_provenance': 'synthetic_native_sample',
                      'control': {}, 'synthetic_diagnostic': True})
        evidence.append({'original_frame': frame, 'replay_frame': frame,
                         'actor_id': 17, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'position_m': position, 'heading_deg': 90,
                                 'speed_mps': 0.0, 'speed_provenance': 'synthetic_native_sample',
                                 'body_vertices_m': [[-.2, y, 0], [.2, y, 0],
                                                     [-.2, y, 1.8], [.2, y, 1.8]]},
                         'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                               'wetness': 0, 'fog_density': 0},
                                   'road_projection': {'road_id': 7, 'section_id': 0,
                                                       'lane_id': -1, 's_m': i / 20}}})
    rows(folder / 'trace.jsonl', trace)
    rows(folder / 'capture/evidence.jsonl', evidence)
    write(folder / 'capture/manifest.json', {'extraction_confirmed': True,
          'frames': 600, 'required_observations': [],
          'sources': {'trace.jsonl': sha(folder / 'trace.jsonl')},
          'synthetic_diagnostic': True})
    (folder / 'capture/recorder_info.txt').write_text('Create 17: walker.pedestrian.0001\n')
    rows(folder / 'capture/native/frames.jsonl', [
        {'frame': row['carla_frame'], 'time_s': row['time_s'],
         'simulation_time': row['time_s'], 'synthetic_diagnostic': True,
         'adapter_graph': f"graphs/base/{row['carla_frame']:08d}.adapter.json"}
        for row in mapping])
    names = ['native-signal-frames.jsonl', 'native-pedestrian-device-frames.jsonl',
             'native-pedestrian-frames.jsonl', 'video_frames.jsonl', 'trace.jsonl',
             'road-boundary.json', 'governing-device-authority.json',
             'highway-authority.json', 'independent-review.json',
             'acquisition-provenance.json', 'capture/evidence.jsonl',
             'capture/manifest.json', 'capture/recorder_info.txt',
             'capture/native/frames.jsonl']
    sources = []
    for name in names:
        path = folder / name
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Diagnostic source exceeds 2 MiB: ' + name)
        sources.append({'path': name, 'source': str(path.relative_to(ROOT)),
                        'sha256': sha(path)})
    generator = {'files': {}, 'graphs': [
        {'path': f"capture/native/graphs/base/{row['carla_frame']:08d}.adapter.json",
         'attributes': {'frame': row['carla_frame']}, 'nodes': [], 'edges': []}
        for row in mapping],
        'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                    'height': height, 'fps': 20, 'color': color}
                   for name, width, height, color in VIEWS]}
    generator_path = HERE / f'selected-v2-{suffix}-generator.json'
    write(generator_path, generator)
    recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
              'generator': {'source': str(generator_path.relative_to(ROOT)),
                            'sha256': sha(generator_path)}}
    recipe_path = HERE / f'selected-v2-{suffix}-recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case': suffix, 'sources': len(sources), 'recipe_sha256': sha(recipe_path)}


if __name__ == '__main__':
    print(json.dumps([build(suffix) for suffix in ('reference', 'contrast')]))
