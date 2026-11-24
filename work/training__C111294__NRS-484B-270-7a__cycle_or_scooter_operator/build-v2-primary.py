"""Return source-hashed current-runtime diagnostic recipes for both primaries."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c111294-v2'
OUT = HERE / 'v2-primary'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location('fixture', HERE / 'saved-fixture-proof.py')
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    base = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    base['format'] = 'worker-execution-manifest'
    base['status'] = 'unselected_current_v2_cpu_primary_proof'
    OUT.mkdir(exist_ok=True)
    for case in ('witness_1', 'witness_2'):
        source = SCRATCH / ('source-' + case)
        if not source.is_dir():
            fixture.make(source, case, full_resolution=True)
        target = OUT / case
        (target / 'sources').mkdir(parents=True, exist_ok=True)
        sources = []
        for path in sorted(source.rglob('*')):
            if not path.is_file() or path.suffix == '.mkv' or 'graphs/base/' in str(path):
                continue
            relative = path.relative_to(source)
            if relative == Path('config.json'):
                continue
            destination = target / 'sources' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            assert destination.stat().st_size <= 2 * 1024 * 1024
            sources.append({'path': str(relative), 'source': str(destination.relative_to(ROOT)),
                            'sha256': sha(destination)})
        graphs = []
        for path in sorted((source / 'capture/native/graphs/base').glob('*.adapter.json')):
            graph = json.loads(path.read_text())
            graphs.append({'path': str(path.relative_to(source)),
                           'attributes': graph.get('metadata', {}),
                           'nodes': graph['nodes'], 'edges': graph['edges']})
        assert len(graphs) == 600
        videos = []
        for name, width, height in (('overview', 1920, 1080), ('approach', 1280, 720),
                                    ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)):
            videos.append({'path': name + '.mkv', 'frames': 600, 'width': width,
                           'height': height, 'fps': 20, 'color': 'black'})
        generator_path = target / 'generator.json'
        generator_path.write_text(json.dumps({'files': {}, 'graphs': graphs, 'videos': videos},
                                             separators=(',', ':')) + '\n')
        assert generator_path.stat().st_size <= 2 * 1024 * 1024
        recipe_path = target / 'recipe.json'
        recipe_path.write_text(json.dumps({'format': 'worker-fixture-recipe',
            'sources': sources, 'generator': {'source': str(generator_path.relative_to(ROOT)),
                                              'sha256': sha(generator_path)}}, indent=2) + '\n')
        manifest = copy.deepcopy(base)
        entry = next(item for item in manifest['cases'] if item['case_id'].endswith('__' + case))
        original = HERE / entry['construction']
        construction = json.loads(original.read_text())
        finalizer = next(item for item in construction['files'] if item['path'] == 'finalize.py')
        needle = 'from measure import measure\n'
        assert finalizer['content'].count(needle) == 1
        finalizer['content'] = finalizer['content'].replace(needle,
            'from measure import measure as _measure\n\n\n'
            'def measure(*args, **kwargs):\n'
            '    return _measure(*args, **kwargs)\n')
        construction_path = target / 'construction.json'
        construction_path.write_text(json.dumps(construction, indent=2) + '\n')
        entry['construction'] = str(construction_path.relative_to(HERE))
        entry['construction_sha256'] = sha(construction_path)
        entry['kind'] = 'unselected_cpu_diagnostic'
        entry['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
        entry['candidates'] = []
        manifest['cases'] = [entry]
        manifest_path = HERE / ('v2-primary-' + case + '-manifest.json')
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({'case': case, 'manifest_sha256': sha(manifest_path),
                          'recipe_sha256': sha(recipe_path),
                          'generator_sha256': sha(generator_path),
                          'sources': len(sources), 'graphs': len(graphs)}))


if __name__ == '__main__':
    main()
