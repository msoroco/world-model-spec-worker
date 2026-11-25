"""Bind source-only marked-line fixtures without claiming physical rendering."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, body):
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + '\n')


def build():
    reports = []
    for index, label in ((1, 'line_stop'), (2, 'line_pass')):
        source = HERE / f'selected-source-probe-{index}'
        target = HERE / f'selected-source-{label}'
        target.mkdir(exist_ok=True)
        for path in sorted(source.rglob('*')):
            if path.is_file():
                destination = target / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
        shutil.copyfile(HERE / 'native/road_stop_line.xodr', target / 'road.xodr')
        case_id = HERE.name + '__' + label
        identity = json.loads((target / 'diagnostic-source-manifest.json').read_text())
        identity['case_id'] = case_id
        identity['sha256']['road.xodr'] = sha(target / 'road.xodr')
        write(target / 'diagnostic-source-manifest.json', identity)
        capture = json.loads((target / 'capture/manifest.json').read_text())
        capture['sources']['road.xodr'] = sha(target / 'road.xodr')
        write(target / 'capture/manifest.json', capture)
        geometry = json.loads((target / 'crosswalk_geometry.json').read_text())
        geometry.pop('crosswalk_near_edge_y_m', None)
        geometry['marked_stop_line_y_m'] = -11
        geometry['road_sha256'] = sha(target / 'road.xodr')
        geometry['source'] = 'authored marked-line OpenDRIVE object; physical rendering unverified'
        write(target / 'crosswalk_geometry.json', geometry)
        spec = HERE / f'current-v2-probe-{index}-fixture-spec.json'
        recipe = HERE / f'selected-{label}-fixture-recipe.json'
        write(recipe, {'format': 'worker-fixture-recipe',
                       'sources': [{'path': p.relative_to(target).as_posix(),
                                    'source': p.relative_to(ROOT).as_posix(),
                                    'sha256': sha(p)}
                                   for p in sorted(target.rglob('*')) if p.is_file()],
                       'generator': {'source': spec.relative_to(ROOT).as_posix(),
                                     'sha256': sha(spec)}})
        contract = json.loads((HERE / f'current-v2-probe-{index}-measurement-contract.json').read_text())
        contract['case_id'] = case_id
        requirement = contract['requirements'][0]
        requirement['disposition_index'] = 1
        requirement['output_key'] = 'marked_line_stop'
        requirement['method'] = 'measure_marked_line_stop'
        write(HERE / f'selected-{label}-measurement-contract.json', contract)
        reports.append({'case_id': case_id, 'recipe_sha256': sha(recipe),
                        'road_sha256': sha(target / 'road.xodr')})
    return reports


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
