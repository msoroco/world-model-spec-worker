"""Bind the existing synthetic saved fixture to the current public CPU check."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main(condition):
    if condition not in ('condition_a', 'condition_b'):
        raise ValueError('Unknown motorcycle condition')
    suffix = '-b' if condition == 'condition_b' else ''
    proof = json.loads((HERE / f'native/current-process-saved-proof{suffix}.json').read_text())
    attempt = Path(proof['source']['attempt'])
    if not attempt.is_dir():
        raise ValueError('Prior synthetic source attempt is unavailable')
    source_folder = HERE / f'current-v2-{condition}-fixture'
    source_folder.mkdir(exist_ok=True)
    excluded = {'config.json', 'construction.json', 'engineering.py', 'controller.py',
                'finalize.py', 'cameras.py', 'geometry.py', 'measure.py', 'runner.py'}
    for source in attempt.rglob('*'):
        if not source.is_file():
            continue
        relative = source.relative_to(attempt)
        if (source.suffix == '.mkv' or relative.parts[:3] == ('capture', 'native', 'graphs')
                or relative.parts[0] == 'tests' or relative.as_posix() in excluded):
            continue
        target = source_folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    evidence = source_folder / 'capture/evidence.jsonl'
    evidence.write_text(evidence.read_text().replace(
        'original_trace_actor_get_velocity', 'synthetic_native_sample'))
    graphs = []
    for source in sorted((attempt / 'capture/native/graphs/base').glob('*.adapter.json')):
        graph = json.loads(source.read_text())
        graphs.append({'path': source.relative_to(attempt).as_posix(),
                       'attributes': graph['metadata'], 'nodes': graph['nodes'],
                       'edges': graph['edges']})
    if len(graphs) != 600:
        raise ValueError('Expected 600 diagnostic adapter graphs')
    spec_path = HERE / f'current-v2-{condition}-fixture-spec.json'
    write(spec_path, {'files': {}, 'graphs': graphs,
                      'videos': [{'path': f'{name}.mkv', 'frames': 600,
                                  'width': width, 'height': height, 'fps': 20,
                                  'color': 'black'} for name, width, height in
                                 [('overview', 1920, 1080), ('approach', 1280, 720),
                                  ('reference_corner', 1280, 720),
                                  ('driver_reference', 1280, 720)]]})
    recipe_path = HERE / f'current-v2-{condition}-fixture-recipe.json'
    sources = [{'path': path.relative_to(source_folder).as_posix(),
                'source': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}
               for path in sorted(source_folder.rglob('*')) if path.is_file()]
    write(recipe_path, {'format': 'worker-fixture-recipe', 'sources': sources,
                        'generator': {'source': spec_path.relative_to(ROOT).as_posix(),
                                      'sha256': sha(spec_path)}})
    contract = json.loads((HERE / f'draft-candidates/{condition}/measurement-contract.json').read_text())
    contract['format'] = 'worker-measurement-contract'
    contract_path = HERE / f'current-v2-{condition}-measurement-contract.json'
    write(contract_path, contract)
    manifest = json.loads((HERE / 'saved-diagnostic-manifest.json').read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'].endswith(condition))
    entry['fixture_recipe'] = recipe_path.relative_to(ROOT).as_posix()
    entry['measurement_contract'] = contract_path.name
    manifest['cases'] = [entry]
    manifest_path = HERE / f'current-v2-{condition}-primary-manifest.json'
    write(manifest_path, manifest)
    print(json.dumps({'manifest_sha256': sha(manifest_path), 'recipe_sha256': sha(recipe_path),
                      'spec_sha256': sha(spec_path), 'sources': len(sources),
                      'graphs': len(graphs)}))


if __name__ == '__main__':
    main(sys.argv[1])
