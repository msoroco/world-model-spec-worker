"""Build source-hashed textual fixtures; all media stays under .runtime-work."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build():
    spec = importlib.util.spec_from_file_location('finalize_fixtures', HERE / 'prove-finalize.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipts = []
    for number, behavior, stem in ((1, 'walk_cycle', 'walk_cycle'),
                                   (2, 'mounted_sidewalk', 'mounted_sidewalk')):
        attempt = module.build_attempt(number, behavior)
        destination = HERE / 'diagnostic-source' / stem
        destination.mkdir(parents=True, exist_ok=True)
        for name in ('bicycle-poses.jsonl', 'restriction-context.json', 'video_frames.jsonl',
                     'road.xodr', 'trace.jsonl', 'acquisition-provenance.json'):
            shutil.copyfile(attempt / name, destination / name)
        rows = [json.loads(line) for line in (destination / 'bicycle-poses.jsonl').read_text().splitlines()]
        frame_rows = []
        evidence = []
        graphs = []
        for i, row in enumerate(rows):
            frame = row['native_frame']
            x, y = row['rider_xy_m']
            graph = f'graphs/base/{frame:08d}.adapter.json'
            frame_rows.append({'frame': frame, 'time_s': row['time_s'],
                               'simulation_time': row['time_s'], 'synthetic_diagnostic': True,
                               'adapter_graph': graph})
            body = [[x + dx, y + dy, z] for dx in (-.9, .9) for dy in (-.3, .3)
                    for z in (0, 1)]
            evidence.append({'original_frame': frame, 'replay_frame': frame,
                             'actor_id': 17, 'recording_time_s': row['time_s'],
                             'replay_simulation_time_s': row['time_s'],
                             'ego': {'position_m': [x, y, 0], 'heading_deg': 0,
                                     'speed_mps': 2.3, 'speed_provenance': 'synthetic_native_sample',
                                     'body_vertices_m': body},
                             'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                                                   'wetness': 0, 'fog_density': 0},
                                       'road_projection': {'road_id': 1, 'section_id': 0,
                                                           'lane_id': -2, 's_m': x + 80}}})
            graphs.append({'path': 'capture/native/' + graph, 'attributes': {'frame': frame},
                           'nodes': [], 'edges': []})
        write(destination / 'capture/native/frames.jsonl',
              ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in frame_rows))
        write(destination / 'capture/evidence.jsonl',
              ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in evidence))
        write(destination / 'capture/recorder_info.txt',
              'Create 17: vehicle.synthetic.bicycle\n' +
              ('Create 19: walker.synthetic.pedestrian\n' if number == 1 else ''))
        write(destination / 'capture/manifest.json', json.dumps({
            'extraction_confirmed': True, 'frames': 600, 'required_observations': [],
            'synthetic_diagnostic': True,
            'sources': {'road.xodr': sha(destination / 'road.xodr'),
                        'trace.jsonl': sha(destination / 'trace.jsonl')}}, indent=2) + '\n')
        generator = {'files': {}, 'graphs': graphs,
                     'videos': [{'path': name + '.mkv', 'frames': 600,
                                 'width': 1920 if name == 'overview' else 1280,
                                 'height': 1080 if name == 'overview' else 720, 'fps': 20,
                                 'color': 'blue'} for name in CAMERAS]}
        generator_path = HERE / f'diagnostic-generator-{stem}.json'
        write(generator_path, json.dumps(generator, separators=(',', ':')) + '\n')
        sources = []
        for path in sorted(destination.rglob('*')):
            if path.is_file():
                relative = path.relative_to(destination)
                sources.append({'path': str(relative), 'source': str(path.relative_to(ROOT)),
                                'sha256': sha(path)})
        recipe = {'format': 'worker-fixture-recipe', 'sources': sources,
                  'generator': {'source': str(generator_path.relative_to(ROOT)),
                                'sha256': sha(generator_path)}}
        recipe_path = HERE / f'diagnostic-recipe-{stem}.json'
        write(recipe_path, json.dumps(recipe, indent=2) + '\n')
        receipts.append({'case_id': f'{HERE.name}__controlled_{number}',
                         'recipe': str(recipe_path.relative_to(HERE)),
                         'recipe_sha256': sha(recipe_path),
                         'source_count': len(sources), 'graph_count': len(graphs)})
    return {'fixtures': receipts, 'diagnostic_only': True,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
