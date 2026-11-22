"""Rebind all selected C111662 construction variants to proved CPU map geometry.

This writes an isolated current-runtime manifest. The selected delivery manifest
remains unchanged until source fidelity and all exact proofs are reviewed.
"""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEST = HERE / 'current-16-experiment'
POLICIES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    selected = json.loads((HERE / 'execution-manifest.json').read_text())
    shared = json.loads((HERE / 'shared-junction-experiment-manifest.json').read_text())
    divided = json.loads((HERE / 'split-divided-experiment-manifest.json').read_text())
    pilots = {entry['case_id'].rsplit('__', 1)[-1]: entry
              for entry in shared['cases'] + divided['cases']}
    manifest = copy.deepcopy(selected)
    manifest['runtime_manifest_sha256'] = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    manifest['status'] = 'isolated_current_runtime_16_construction_probe'
    proofs = {}
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        pilot = pilots[suffix]
        prototype = json.loads((HERE / pilot['construction']).read_text())
        prototype_files = {item['path']: item['content'] for item in prototype['files']}
        road = prototype_files['road.xodr']
        road_sha = hashlib.sha256(road.encode()).hexdigest()
        modified_scripts = ('native/build.py', 'native/check.py', 'native/capture.py') if suffix in ('reference', 'contrast') else (
            'native/divided_opening.py', 'native/capture_divided.py',
            'native/process_original_divided.py')
        for candidate in POLICIES:
            original_ref = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            original = json.loads((HERE / original_ref['construction']).read_text())
            content_paths = {item['path'] for item in original['files']}
            if content_paths != set(prototype_files):
                raise ValueError('Candidate file inventory differs: ' + suffix + '/' + candidate)
            for item in original['files']:
                path = item['path']
                if path.endswith('.xodr'):
                    item['content'] = road
                elif path.endswith('config.json'):
                    config = json.loads(item['content'])
                    if 'road_sha256' in config:
                        config['road_sha256'] = road_sha
                    item['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
                elif any(path.endswith('/' + name) for name in modified_scripts) or (
                        suffix.startswith('divided_') and path == 'tests/test_divided.py'):
                    item['content'] = prototype_files[path]
            target = DEST / suffix / candidate / 'construction.json'
            write(target, original)
            original_ref['construction'] = str(target.relative_to(HERE))
            original_ref['construction_sha256'] = sha(target)
            proofs[suffix + '/' + candidate] = {'construction_sha256': sha(target),
                                                 'road_sha256': road_sha}
        entry['fixture_recipe'] = pilot['fixture_recipe']
        entry['preparation_status'] = 'isolated current-runtime construction; selected proof pending'
    output = HERE / 'current-16-experiment-manifest.json'
    write(output, manifest)
    write(DEST / 'construction-index.json', {'format': 'c111662-current-16-construction-index-v1',
                                              'manifest_sha256': sha(output), 'variants': proofs})
    print(json.dumps({'manifest_sha256': sha(output), 'variants': len(proofs)}))


if __name__ == '__main__':
    main()
