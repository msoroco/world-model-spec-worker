"""Export two current source-hashed 480-frame C10014 diagnostic recipes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ('native_samples.jsonl', 'road_geometry.json', 'context.json',
         'video_frames.jsonl', 'body_history.jsonl', 'trace.jsonl',
         'capture/evidence.jsonl', 'capture/manifest.json',
         'capture/native/frames.jsonl', 'capture/recorder_info.txt', 'road.xodr')
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def load_probe():
    spec = importlib.util.spec_from_file_location('c10014_current_probe',
                                                  HERE/'probe-core-synthetic.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build():
    probe = load_probe()
    produced = []
    for suffix in ('reference', 'contrast'):
        with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',
                                         prefix='c10014-recipe-source-') as temporary:
            source = Path(temporary)/'attempt'
            probe.make_attempt(source, suffix)
            files = {name: (source/name).read_text() for name in NAMES}
            samples = rows(source/'native_samples.jsonl')
            evidence = rows(source/'capture/evidence.jsonl')
            frames = rows(source/'capture/native/frames.jsonl')
            if len(samples) != len(evidence) or len(samples) != len(frames) or len(samples) != 480:
                raise ValueError('Diagnostic source frame count changed')
            if not all(row.get('speed_provenance') == 'synthetic_native_sample'
                       for row in samples):
                raise ValueError('Invented speed lacks diagnostic provenance')
            graphs = []
            for sample, event, frame in zip(samples, evidence, frames):
                x, y = sample['native_center_xy_m']
                graphs.append({'path': 'capture/native/'+frame['base'],
                               'attributes': {'frame': frame['frame'],
                                              'simulation_time_s': frame['time_s'],
                                              'synthetic_diagnostic': True,
                                              'source': 'C10014 synthetic saved vehicle rows'},
                               'nodes': [{'id': 'ego', 'attributes': {
                                   'sem_class': 'ego', 'entity_id': 107,
                                   'vertex': [x, y, .5], 'forward': [1., 0., 0.],
                                   'threedbbox': event['ego']['body_vertices_m']}}],
                               'edges': []})
            videos = [{'path': name+'.mkv', 'frames': 480, 'width': width,
                       'height': height, 'fps': 20, 'color': 'black'}
                      for name, width, height in CAMERAS]
            spec = {'files': files, 'graphs': graphs, 'videos': videos}
            target = HERE/f'update015-diagnostic-{suffix}.json'
            target.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False)+'\n')
            if target.stat().st_size >= 2*1024*1024:
                raise ValueError('Diagnostic specification exceeds worker text limit')
            relative = target.relative_to(ROOT).as_posix()
            digest = sha(target)
            recipe = {'format': 'worker-fixture-recipe',
                      'sources': [{'path': 'diagnostic-input.json',
                                   'source': relative, 'sha256': digest}],
                      'generator': {'source': relative, 'sha256': digest}}
            recipe_path = HERE/f'update015-diagnostic-{suffix}-recipe.json'
            recipe_path.write_text(json.dumps(recipe, indent=2)+'\n')
            produced.append({'suffix': suffix, 'source_sha256': digest,
                             'recipe_sha256': sha(recipe_path),
                             'frames': len(samples), 'graphs': len(graphs),
                             'cameras': len(videos)})
    summary = {'format': 'c10014-update015-diagnostic-recipes',
               'recipes': produced,
               'scope': 'synthetic CPU sources; no original Native or legal acceptance'}
    (HERE/'update015-recipe-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    build()
