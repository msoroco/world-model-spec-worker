"""Inventory exact synthetic saved frames as current CPU diagnostic recipes."""
import hashlib
import json
import pickle
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from probe_compat import fixture


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, separators=(',', ':')) + '\n')


def build(case):
    temporary = REPO / '.runtime-work' / f'update015-c111331-{case}-source'
    if temporary.exists():
        shutil.rmtree(temporary)
    fixture(temporary, case, 'primary', text_only=True)
    files = {}
    for source in temporary.rglob('*'):
        if source.is_file() and source.suffix not in ('.mkv', '.pkl'):
            relative = source.relative_to(temporary).as_posix()
            files[relative] = source.read_text()
    capture_manifest = json.loads(files['capture/manifest.json'])
    capture_manifest['acquisition'] = 'synthetic_cpu_fixture'
    files['capture/manifest.json'] = json.dumps(capture_manifest, indent=2) + '\n'
    files['acquisition-provenance.json'] = json.dumps({
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'native_executed': False}) + '\n'
    evidence = [json.loads(line) for line in files['capture/evidence.jsonl'].splitlines()]
    for row in evidence:
        row['ego']['speed_provenance'] = 'synthetic_native_sample'
    files['capture/evidence.jsonl'] = ''.join(json.dumps(row) + '\n' for row in evidence)
    graphs = []
    for source in sorted((temporary / 'capture/native/graphs/base').glob('*.pkl')):
        graph = pickle.loads(source.read_bytes())
        graphs.append({'path': source.relative_to(temporary).as_posix(),
                       'attributes': dict(graph.graph),
                       'nodes': [{'id': str(node), 'attributes': dict(attributes)}
                                 for node, attributes in graph.nodes(data=True)],
                       'edges': [{'source': str(a), 'target': str(b),
                                  'attributes': dict(attributes)}
                                 for a, b, attributes in graph.edges(data=True)]})
    videos = [{'path': name + '.mkv', 'frames': 480, 'width': width,
               'height': height, 'fps': 20, 'color': color}
              for name, width, height, color in (
                  ('overview', 1920, 1080, 'blue'),
                  ('approach', 1280, 720, 'green'),
                  ('reference_corner', 1280, 720, 'white'),
                  ('driver_reference', 1280, 720, 'red'))]
    spec = HERE / f'update015-{case}-diagnostic.json'
    recipe = HERE / f'update015-{case}-recipe.json'
    if spec.is_file():
        previous = json.loads(spec.read_text())
        if set(previous['files']) != set(files):
            raise ValueError('Diagnostic source file inventory changed')
        files = {name: files[name] for name in previous['files']}
    write(spec, {'files': files, 'graphs': graphs, 'videos': videos})
    relative = spec.relative_to(REPO).as_posix()
    write(recipe, {'format': 'worker-fixture-recipe',
                   'sources': [{'path': 'diagnostic-input.json',
                                'source': relative,
                                'sha256': sha(spec)}],
                   'generator': {'source': relative, 'sha256': sha(spec)}})
    print(case, len(graphs), spec.stat().st_size, sha(recipe))


if __name__ == '__main__':
    for item in ('reference', 'contrast'):
        build(item)
