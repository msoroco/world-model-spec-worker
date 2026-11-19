"""Bind explicit, source-hashed diagnostic inputs for exact red-entry cases."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE_NAMES = ('signal_vehicle_history.jsonl', 'video_frames.jsonl',
                'junction_context.json', 'trace.jsonl', 'acquisition-provenance.json',
                'capture/evidence.jsonl', 'capture/manifest.json',
                'capture/native/frames.jsonl', 'capture/recorder_info.txt')
VIDEOS = (('overview.mkv', 1920, 1080, 'black'),
          ('approach.mkv', 1280, 720, 'green'),
          ('reference_corner.mkv', 1280, 720, 'blue'),
          ('driver_reference.mkv', 1280, 720, 'red'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('entry_at_red', 'entry_after_red', 'stops_on_yellow'), default='entry_at_red')
    args = parser.parse_args()
    stem = {'entry_at_red': 'at-red', 'entry_after_red': 'after-red', 'stops_on_yellow': 'yellow-stop'}[args.case]
    attempt = REPO / ('.runtime-work/c158196-yellow-red-' + stem + '-recorded-only/acquisition')
    spec = HERE / (stem + '-diagnostic-sources.json')
    recipe_path = HERE / (stem + '-fixture-recipe.json')
    files = {name: (attempt / name).read_text() for name in SOURCE_NAMES}
    graphs = []
    for kind in ('abstract', 'base'):
        for frame in range(900):
            name = f'capture/native/graphs/{kind}/{frame:08d}.adapter.json'
            graph = json.loads((attempt / name).read_text())
            if graph['format'] != 'native-adapter-graph-v1' or graph['nodes'] or graph['edges']:
                raise ValueError('Unexpected diagnostic graph: ' + name)
            graphs.append({'path': name, 'attributes': graph['metadata'],
                           'nodes': graph['nodes'], 'edges': graph['edges']})
    videos = [{'path': name, 'frames': 900, 'width': width,
               'height': height, 'fps': 20, 'color': color}
              for name, width, height, color in VIDEOS]
    for video in videos:
        if not (attempt / video['path']).is_file():
            raise ValueError('Missing source camera: ' + video['path'])
    spec.write_text(json.dumps({'files': files, 'graphs': graphs, 'videos': videos},
                               separators=(',', ':'), allow_nan=False) + '\n')
    if spec.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Explicit source specification exceeds per-file return cap')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'road.xodr',
                           'source': 'work/' + HERE.name + '/yellow-red-site.xodr',
                           'sha256': sha(HERE / 'yellow-red-site.xodr')}],
              'generator': {'source': 'work/' + HERE.name + '/' + spec.name,
                            'sha256': sha(spec)}}
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    print(json.dumps({'case_id': HERE.name + '__' + args.case,
                      'spec_bytes': spec.stat().st_size, 'spec_sha256': sha(spec),
                      'recipe_sha256': sha(recipe_path), 'graphs': len(graphs)}))


if __name__ == '__main__':
    main()
