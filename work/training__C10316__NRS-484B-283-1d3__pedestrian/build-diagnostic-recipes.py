"""Inventory retained synthetic raw inputs for current runtime compatibility."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    spec = importlib.util.spec_from_file_location('probe', HERE / 'probe-package-no-countdown.py')
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    for suffix in ('controlled_1', 'controlled_2'):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as temporary:
            fixture = Path(temporary) / 'fixture'
            probe.fixture_at(fixture, suffix)
            files = {}
            graphs = []
            for path in sorted(fixture.rglob('*')):
                if not path.is_file() or path.suffix == '.mkv' or 'channels' in path.relative_to(fixture).parts:
                    continue
                relative = str(path.relative_to(fixture))
                if path.suffix == '.pkl':
                    graph = pickle.loads(path.read_bytes())
                    graphs.append({'path': relative, 'attributes': dict(graph.graph),
                                   'nodes': [{'id': key, 'attributes': dict(value)} for key, value in graph.nodes(data=True)],
                                   'edges': [{'source': a, 'target': b, 'attributes': dict(value)}
                                             for a, b, value in graph.edges(data=True)]})
                else:
                    files[relative] = path.read_text()
            videos = [{'path': name + '.mkv', 'frames': 240, 'width': width,
                       'height': height, 'fps': 20, 'color': 'black'}
                      for name, width, height in (('overview', 1920, 1080), ('approach', 1280, 720),
                                                  ('reference_corner', 1280, 720),
                                                  ('driver_reference', 1280, 720))]
            diagnostic = HERE / ('diagnostic-' + suffix + '.json')
            diagnostic.write_text(json.dumps({'files': files, 'graphs': graphs, 'videos': videos},
                                             separators=(',', ':')) + '\n')
            relative = str(diagnostic.relative_to(ROOT))
            recipe = {'format': 'worker-fixture-recipe',
                      'sources': [{'path': 'diagnostic-input.json', 'source': relative,
                                   'sha256': sha(diagnostic)}],
                      'generator': {'source': relative, 'sha256': sha(diagnostic)}}
            (HERE / ('diagnostic-' + suffix + '-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')
            print(suffix, len(files), len(graphs), len(videos), diagnostic.stat().st_size)


if __name__ == '__main__':
    build()
