"""Build C24805-specific synthetic source fixtures and source-hashed recipes.

These inputs exercise the saved pipeline; they do not claim physical visibility.
"""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SOURCE = ROOT / 'work/training__C111325__NRS-484A-450-2__motor_vehicle_driver'
OLD = 'training__C111325__NRS-484A-450-2__motor_vehicle_driver'
NEW = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def build():
    report = []
    for source_suffix, suffix, index in (('stop', 'probe_a', 1),
                                         ('pass', 'probe_b', 2)):
        source = SOURCE / f'selected-source-sight_{source_suffix}'
        target = HERE / f'selected-source-{suffix}'
        for path in sorted(source.rglob('*')):
            if not path.is_file():
                continue
            destination = target / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            content = path.read_text().replace(OLD, NEW)
            content = content.replace('sight_' + source_suffix, suffix)
            destination.write_text(content.rstrip() + '\n')
        (target / 'road.xodr').write_text((HERE / 'native/road.xodr').read_text())
        identity_path = target / 'diagnostic-source-manifest.json'
        identity = json.loads(identity_path.read_text())
        identity['case_id'] = NEW + '__' + suffix
        for name in identity['sha256']:
            identity['sha256'][name] = sha(target / name)
        write(identity_path, identity)
        capture_path = target / 'capture/manifest.json'
        capture = json.loads(capture_path.read_text())
        for name in capture['sources']:
            capture['sources'][name] = sha(target / name)
        write(capture_path, capture)
        geometry_path = target / 'crosswalk_geometry.json'
        geometry = json.loads(geometry_path.read_text())
        geometry['road_sha256'] = sha(target / 'road.xodr')
        geometry['source'] = ('C24805 authored no-reference road and synthetic '
                              'view proxy; physical visibility unverified')
        write(geometry_path, geometry)
        spec_source = SOURCE / f'current-v2-probe-{index}-fixture-spec.json'
        spec_target = HERE / f'selected-{suffix}-fixture-spec.json'
        spec_target.write_text(spec_source.read_text().rstrip() + '\n')
        recipe = {
            'format': 'worker-fixture-recipe',
            'sources': [{'path': path.relative_to(target).as_posix(),
                         'source': path.relative_to(ROOT).as_posix(),
                         'sha256': sha(path)}
                        for path in sorted(target.rglob('*')) if path.is_file()],
            'generator': {'source': spec_target.relative_to(ROOT).as_posix(),
                          'sha256': sha(spec_target)},
        }
        recipe_target = HERE / f'selected-{suffix}-fixture-recipe.json'
        write(recipe_target, recipe)
        contract_source = SOURCE / f'selected-sight_{source_suffix}-measurement-contract.json'
        contract = json.loads(contract_source.read_text())
        contract['case_id'] = NEW + '__' + suffix
        contract['requirements'][0]['disposition_index'] = 0
        contract_target = HERE / f'selected-{suffix}-measurement-contract.json'
        write(contract_target, contract)
        report.append({'case_id': NEW + '__' + suffix,
                       'source_manifest_sha256': sha(identity_path),
                       'recipe_sha256': sha(recipe_target),
                       'contract_sha256': sha(contract_target)})
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    build()
