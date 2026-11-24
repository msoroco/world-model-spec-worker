"""Build an explicit current-runtime 600-frame diagnostic for one right-turn primary."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT', str(ROOT / '.runtime-work/c110919-current'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    suffix = sys.argv[1] if len(sys.argv) > 1 else 'probe_a'
    if suffix not in ('probe_a', 'probe_b'):
        raise ValueError('Unknown controlled right-turn case')
    module_spec = importlib.util.spec_from_file_location('saved', HERE / 'saved-fixture-proof.py')
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    source_folder = HERE / f'current-v2-{suffix}-fixture'
    source_folder.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c110919-v2-source-') as temp:
        generated = Path(temp) / 'generated'
        module.make_attempt(generated, suffix, full_resolution=True)
        for source in generated.rglob('*'):
            if not source.is_file():
                continue
            relative = source.relative_to(generated)
            if source.suffix == '.mkv' or relative.parts[:3] == ('capture','native','graphs') or relative.as_posix() in (
                    'config.json','capture/native/frames.jsonl','capture/recorder_info.txt'):
                continue
            target = source_folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        trace = [json.loads(line) for line in (source_folder / 'trace.jsonl').read_text().splitlines()]
        graphs = []
        for row in trace:
            frame = row['frame']
            graphs.append({'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
                           'attributes': {'frame': frame, 'simulation_time_s': row['time_s'],
                                          'units': 'm', 'observed_evidence': 'synthetic_diagnostic'},
                           'nodes': [{'id': 'ego', 'attributes': {
                               'sem_class': 'vehicle.lincoln.mkz_2020', 'carla_id': 107,
                               'vertex': row['position_m']}}], 'edges': []})
        spec_path = HERE / f'current-v2-{suffix}-fixture-spec.json'
        spec = {'files': {
            'capture/native/frames.jsonl': (generated / 'capture/native/frames.jsonl').read_text(),
            'capture/recorder_info.txt': (generated / 'capture/recorder_info.txt').read_text()},
            'graphs': graphs,
            'videos': [{'path': f'{name}.mkv', 'frames': 600, 'width': width, 'height': height,
                        'fps': 20, 'color': 'black'} for name, width, height in
                       [('overview',1920,1080), ('approach',1280,720),
                        ('reference_corner',1280,720), ('driver_reference',1280,720)]]}
        write(spec_path, spec)
    recipe_path = HERE / f'current-v2-{suffix}-fixture-recipe.json'
    sources = [{'path': path.relative_to(source_folder).as_posix(),
                'source': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}
               for path in sorted(source_folder.rglob('*')) if path.is_file()]
    write(recipe_path, {'format': 'worker-fixture-recipe', 'sources': sources,
                        'generator': {'source': spec_path.relative_to(ROOT).as_posix(),
                                      'sha256': sha(spec_path)}})
    contract = json.loads((HERE / f'draft-candidates/{suffix}/measurement-contract.json').read_text())
    contract['format'] = 'worker-measurement-contract'
    contract_path = HERE / f'current-v2-{suffix}-measurement-contract.json'
    write(contract_path, contract)
    original = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    entry = next(c for c in original['cases'] if c['case_id'] == HERE.name + '__' + suffix)
    entry['candidates'] = []
    entry['fixture_recipe'] = recipe_path.relative_to(ROOT).as_posix()
    entry['measurement_contract'] = contract_path.name
    original['cases'] = [entry]
    manifest_path = HERE / f'current-v2-{suffix}-primary-manifest.json'
    write(manifest_path, original)
    print(json.dumps({'manifest_sha256': sha(manifest_path), 'recipe_sha256': sha(recipe_path),
                      'spec_sha256': sha(spec_path), 'sources': len(sources)}))


if __name__ == '__main__':
    main()
