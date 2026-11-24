"""Pin the current 600-frame diagnostic raw sources to a public fixture recipe."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = (
    'native_samples.jsonl', 'body_history.jsonl', 'trace.jsonl',
    'capture/evidence.jsonl', 'capture/manifest.json',
    'capture/native/frames.jsonl', 'capture/recorder_info.txt',
    'video_frames.jsonl', 'road_geometry.json', 'road.xodr',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(case):
    receipt = json.loads((HERE / 'native' / f'current-core-{case}.log').read_text())
    source = Path(receipt['scratch']) / 'attempt'
    if not source.is_dir():
        raise ValueError('Retained current raw diagnostic is missing')
    files = {name: (source / name).read_text() for name in RAW}
    frames = [json.loads(line) for line in files['capture/native/frames.jsonl'].splitlines()]
    if len(frames) != 600:
        raise ValueError('Current raw diagnostic frame count differs')
    graphs = []
    for row in frames:
        path = 'capture/native/' + row['adapter_graph']
        graph = json.loads((source / path).read_text())
        graphs.append({'path': path, 'attributes': graph['metadata'],
                       'nodes': graph['nodes'], 'edges': graph['edges']})
    videos = [{'path': name + '.mkv', 'frames': 600, 'width': width,
               'height': height, 'fps': 20, 'color': 'black'}
              for name, width, height in (
                  ('overview', 1920, 1080), ('approach', 1280, 720),
                  ('reference_corner', 1280, 720),
                  ('driver_reference', 1280, 720))]
    diagnostic = HERE / f'current-{case}-diagnostic.json'
    diagnostic.write_text(json.dumps({'files': files, 'graphs': graphs,
                                      'videos': videos}, separators=(',', ':')) + '\n')
    if diagnostic.stat().st_size > 2 * 1024 * 1024:
        diagnostic.unlink()
        raise ValueError('Diagnostic exceeds returned file size limit')
    relative = diagnostic.relative_to(ROOT).as_posix()
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': relative,
                           'sha256': sha(diagnostic)}],
              'generator': {'source': relative, 'sha256': sha(diagnostic)}}
    recipe_path = HERE / f'current-{case}-recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    return {'case': case, 'frames': len(frames), 'graphs': len(graphs),
            'camera_sources': len(videos), 'diagnostic_sha256': sha(diagnostic),
            'recipe_sha256': sha(recipe_path), 'selected': False}


if __name__ == '__main__':
    print(json.dumps([build(case) for case in ('witness_1', 'witness_2')], indent=2))
