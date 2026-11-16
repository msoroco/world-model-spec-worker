"""Freeze an exact signal-distance Native diagnostic as a text recipe."""
import hashlib
import argparse
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--feet', type=int, choices=(90,100,110,290,300,310), default=300)
    parser.add_argument('--candidate', choices=('primary', 'fallback1'), default='primary')
    args = parser.parse_args()
    candidate = args.candidate
    feet = args.feet
    construction = json.loads((HERE / 'draft-candidates' / str(feet) / candidate / 'construction.json').read_text())
    config = json.loads(next(x['content'] for x in construction['files'] if x['path'] == 'config.json'))
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as temporary:
        source = Path(temporary) / 'source'
        module.build_fixture(source, feet, config)
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
        label = 'diagnostic-' + str(feet) + ('-fallback1' if candidate == 'fallback1' else '')
        spec = HERE / (label + '.json')
        spec.write_text(json.dumps({'files': files, 'graphs': graphs,
                                    'videos': videos}, separators=(',', ':')) + '\n')
    assignment = ROOT / 'inputs' / HERE.name / 'assignment.json'
    recipe = HERE / (label + '-recipe.json')
    recipe.write_text(json.dumps({'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-input-assignment.json',
                     'source': str(assignment.relative_to(ROOT)), 'sha256': sha(assignment)}],
        'generator': {'source': str(spec.relative_to(ROOT)), 'sha256': sha(spec)}}, indent=2) + '\n')
    print(json.dumps({'spec_bytes': spec.stat().st_size, 'spec_sha256': sha(spec)}))


if __name__ == '__main__':
    main()
