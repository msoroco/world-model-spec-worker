"""Build a current-runtime diagnostic recipe from the retained witness source."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(suffix='witness_1'):
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if ROOT / '.runtime-work' not in output_root.parents:
        raise ValueError('Current diagnostic output root must be under .runtime-work')
    module = importlib.util.spec_from_file_location('steady_probe', HERE / 'probe-package-steady.py')
    probe = importlib.util.module_from_spec(module)
    module.loader.exec_module(probe)
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c10316-d4-recipe-') as temp:
        fixture = Path(temp) / 'fixture'
        probe.fixture_at(fixture, suffix)
        evidence = [json.loads(line) for line in (fixture / 'capture/evidence.jsonl').read_text().splitlines()]
        for row in evidence:
            row['ego']['speed_provenance'] = 'synthetic_native_sample'
        (fixture / 'capture/evidence.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in evidence))
        frames = [json.loads(line) for line in (fixture / 'capture/native/frames.jsonl').read_text().splitlines()]
        for row in frames:
            row['base'] = str(Path(row['base']).with_suffix('.adapter.json'))
        (fixture / 'capture/native/frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in frames))
        files, graphs = {}, []
        for path in sorted(fixture.rglob('*')):
            if not path.is_file() or path.suffix == '.mkv' or 'channels' in path.relative_to(fixture).parts:
                continue
            relative = path.relative_to(fixture).as_posix()
            if path.suffix == '.pkl':
                graph = pickle.loads(path.read_bytes())
                graphs.append({'path': str(Path(relative).with_suffix('.adapter.json')),
                               'attributes': dict(graph.graph),
                               'nodes': [{'id': node, 'attributes': dict(attrs)}
                                         for node, attrs in graph.nodes(data=True)],
                               'edges': [{'source': start, 'target': end, 'attributes': dict(attrs)}
                                         for start, end, attrs in graph.edges(data=True)]})
            else:
                files[relative] = path.read_text()
        videos = [{'path': name + '.mkv', 'frames': 240, 'width': width, 'height': height,
                   'fps': 20, 'color': 'black'}
                  for name, width, height in (('overview', 1920, 1080),
                                              ('approach', 1280, 720),
                                              ('reference_corner', 1280, 720),
                                              ('driver_reference', 1280, 720))]
        diagnostic = HERE / ('current-' + suffix + '-diagnostic.json')
        diagnostic.write_text(json.dumps({'files': files, 'graphs': graphs, 'videos': videos},
                                         separators=(',', ':')) + '\n')
        relative = diagnostic.relative_to(ROOT).as_posix()
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json', 'source': relative,
                               'sha256': sha(diagnostic)}],
                  'generator': {'source': relative, 'sha256': sha(diagnostic)}}
        (HERE / ('current-' + suffix + '-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')
        return {'suffix': suffix, 'files': len(files), 'graphs': len(graphs),
                'videos': len(videos), 'diagnostic_bytes': diagnostic.stat().st_size,
                'diagnostic_sha256': sha(diagnostic)}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
