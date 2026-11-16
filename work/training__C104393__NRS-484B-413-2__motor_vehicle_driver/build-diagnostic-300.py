"""Freeze the 300-foot synthetic Native source as a current-runtime text recipe."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
loader = importlib.util.spec_from_file_location('package_probe', HERE / 'probe-package-compatibility.py')
module = importlib.util.module_from_spec(loader)
loader.loader.exec_module(module)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    construction = json.loads((HERE / 'draft-candidates/300/primary/construction.json').read_text())
    config = json.loads(next(x['content'] for x in construction['files'] if x['path'] == 'config.json'))
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as temporary:
        source = Path(temporary) / 'source'
        module.build_fixture(source, 300, config)
        files = {}
        for path in source.rglob('*'):
            if path.is_file() and path.suffix != '.mkv' and '/graphs/' not in str(path):
                files[str(path.relative_to(source))] = path.read_text()
        graphs = []
        for index in range(840):
            frame = 1000 + index
            graphs.append({'path': f'capture/native/graphs/base/{frame:08d}.pkl',
                           'attributes': {'frame': frame}, 'nodes': [], 'edges': []})
        videos = [{'path': name + '.mkv', 'frames': 840, 'width': width,
                   'height': height, 'fps': 20, 'color': 'black'}
                  for name, width, height in
                  (('overview', 1920, 1080), ('approach', 1280, 720),
                   ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))]
        spec = HERE / 'diagnostic-300.json'
        spec.write_text(json.dumps({'files': files, 'graphs': graphs,
                                    'videos': videos}, separators=(',', ':')) + '\n')
    assignment = ROOT / 'inputs' / HERE.name / 'assignment.json'
    recipe = HERE / 'diagnostic-300-recipe.json'
    recipe.write_text(json.dumps({'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-input-assignment.json',
                     'source': str(assignment.relative_to(ROOT)), 'sha256': sha(assignment)}],
        'generator': {'source': str(spec.relative_to(ROOT)), 'sha256': sha(spec)}}, indent=2) + '\n')
    print(json.dumps({'spec_bytes': spec.stat().st_size, 'spec_sha256': sha(spec)}))


if __name__ == '__main__':
    main()
