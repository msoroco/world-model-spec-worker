"""Build source-hashed, current-format 600-frame CPU diagnostic recipe."""
import hashlib
import argparse
import importlib.util
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT', str(ROOT / '.runtime-work' / 'owner194'))

spec = importlib.util.spec_from_file_location('saved_fixture', FOLDER / 'saved-fixture-proof.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, value):
    Path(path).write_text(json.dumps(value, separators=(',', ':')) + '\n')

def main(case):
    scratch = ROOT / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix='owner194-v2-') as tmp:
        fixture = Path(tmp) / 'fixture'
        module.make_attempt(fixture, case, full_resolution=True)
        files = {}
        for path in fixture.rglob('*'):
            if not path.is_file() or path.suffix == '.mkv' or path.name.endswith('.adapter.json'):
                continue
            relative = str(path.relative_to(fixture))
            if relative == 'config.json' or relative.startswith('channels/'):
                continue
            files[relative] = path.read_text()
    graphs = []
    for frame in range(100, 700):
        graphs.append({'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
                       'attributes': {'frame': frame, 'synthetic_diagnostic': True},
                       'nodes': [], 'edges': []})
    videos = [dict(path=name + '.mkv', frames=600, width=width, height=height, fps=20, color='black')
              for name, width, height in [('overview', 1920, 1080), ('approach', 1280, 720),
                                          ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]]
    suffix = 'primary' if case == 'controlled_1' else case
    generator = FOLDER / f'current-v2-{suffix}-generator.json'
    write(generator, {'files': files, 'graphs': graphs, 'videos': videos})
    assignment = ROOT / 'inputs' / FOLDER.name / 'assignment.json'
    recipe = FOLDER / f'current-v2-{suffix}-recipe.json'
    write(recipe, {'format': 'worker-fixture-recipe',
                   'sources': [{'path': 'diagnostic-input-assignment.json',
                                'source': str(assignment.relative_to(ROOT)), 'sha256': sha(assignment)}],
                   'generator': {'source': str(generator.relative_to(ROOT)), 'sha256': sha(generator)}})
    print(json.dumps({'generator_sha256': sha(generator), 'recipe_sha256': sha(recipe),
                      'generator_bytes': generator.stat().st_size, 'files': len(files), 'graphs': len(graphs)}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('controlled_1', 'controlled_2'), default='controlled_1')
    main(parser.parse_args().case)
