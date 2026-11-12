"""Bind the source-consistent diagnostic T junction to both official cases."""

import json
from hashlib import sha256
from pathlib import Path

from official_diagnostic_geometry import rebuild


HERE = Path(__file__).resolve().parent


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def attach():
    finalizer = (HERE / 'ending_road_official_finalizer.py').read_text()
    auditor = (HERE / 'official_geometry_source_audit.py').read_text()
    binding = (HERE / 'official_geometry_binding.py').read_text()
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for label, suffix in (('device', 'official_device_control'),
                          ('green', 'official_device_green_phase')):
        diagnostic_path = HERE / f'diagnostic-official-{label}.json'
        diagnostic_path.write_text(json.dumps(
            rebuild(json.loads(diagnostic_path.read_text())), separators=(',', ':')) + '\n')
        recipe_path = HERE / f'diagnostic-recipe-official-{label}.json'
        recipe = json.loads(recipe_path.read_text())
        recipe['sources'][0]['sha256'] = digest(diagnostic_path)
        recipe['generator']['sha256'] = digest(diagnostic_path)
        write_json(recipe_path, recipe)
        contract_path = HERE / f'measurement-contract-official-{label}.json'
        contract = json.loads(contract_path.read_text())
        for requirement in contract['requirements']:
            if requirement['output_key'] == 'official_device_observation':
                requirement['inputs'] = list(dict.fromkeys(requirement['inputs'] + [
                    'official_geometry_binding.json', 'road.xodr']))
        contract['negative'] = {
            'remove': ['official_geometry_binding.json'],
            'error_contains': 'Missing required source: official_geometry_binding.json',
        }
        write_json(contract_path, contract)
        entry = next(row for row in manifest['cases'] if row['case_id'].endswith('__' + suffix))
        entry['acquisition']['official_geometry_binding'] = {
            'entrypoint': 'official_geometry_source_audit.py',
            'method': 'hash and map/source route/device join on retained originals',
            'evidence': 'official_geometry_binding.json, road.xodr, intersection_topology.json and official_device_context.json',
        }
        for target in [entry] + entry['candidates']:
            path = HERE / target['construction']
            construction = json.loads(path.read_text())
            files = {row['path']: row for row in construction['files']}
            files['ending_road_official_finalizer.py']['content'] = finalizer
            files['official_geometry_binding.py']['content'] = binding
            files['official_geometry_source_audit.py'] = {
                'path': 'official_geometry_source_audit.py', 'content': auditor}
            construction['files'] = list(files.values())
            write_json(path, construction)
            target['construction_sha256'] = digest(path)
    write_json(manifest_path, manifest)


if __name__ == '__main__':
    attach()
