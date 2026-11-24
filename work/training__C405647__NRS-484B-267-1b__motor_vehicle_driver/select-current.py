"""Select six source-exact candidates under the current runtime contract."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = {'front_lamp': 'approach', 'right_edge': 'reference_corner',
         'rear_approach': 'driver_reference'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    source['runtime_manifest_sha256'] = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    source['status'] = 'delivery_prepared'
    source['format'] = 'worker-execution-manifest'
    source['delivery_ready'] = False
    source['original_native_observed'] = False
    contract = json.loads((HERE / 'native/selected-measurement-contract.json').read_text())
    contract = json.loads(json.dumps(contract).replace('source-scope.json', 'context-scope.json'))
    for case in source['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        case['kind'] = 'delivery'
        case['candidates'] = case['candidates'][:2]
        case['fixture_recipe'] = (HERE.relative_to(ROOT) /
                                  f'current-{suffix}-recipe.json').as_posix()
        target_contract = HERE / 'current-contracts' / (suffix + '.json')
        target_contract.parent.mkdir(exist_ok=True)
        target_contract.write_text(json.dumps(contract, indent=2) + '\n')
        case['measurement_contract'] = target_contract.relative_to(HERE).as_posix()
        for item in [case] + case['candidates']:
            construction = json.loads((HERE / item['construction']).read_text())
            for file in construction['files']:
                if file['path'] == 'finalize.py':
                    file['content'] = (HERE / 'native/finalize-current.py').read_text().replace(
                        'source-scope.json', 'context-scope.json')
                else:
                    for old, new in NAMES.items():
                        file['content'] = file['content'].replace(old, new)
                    file['content'] = file['content'].replace('source-scope.json',
                                                              'context-scope.json')
                if file['path'] == 'config.json':
                    config = json.loads(file['content'])
                    config['camera_plan'] = [NAMES.get(x, x) for x in config['camera_plan']]
                    for camera in config['cameras']:
                        camera['name'] = NAMES.get(camera['name'], camera['name'])
                        camera['fov_deg'] = {'overview': 80, 'approach': 70,
                                             'reference_corner': 75,
                                             'driver_reference': 90}[camera['name']]
                    file['content'] = json.dumps(config, indent=2) + '\n'
            channels = construction['recording_description']['channels']
            template = channels[0]
            for name in ('ego_pose', 'ego_speed', 'right_edge_clear_intersection_position',
                         'rel.same_direction', 'rel.surface_gap', 'kin.position', 'rel.occupies'):
                channels.append({**template, 'name': name,
                                 'method': 'Saved 600-frame Native actor, map and camera joins',
                                 'unit': 'structured'})
            target = HERE / 'current-bundles' / suffix / item['id'] / 'construction.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(construction, indent=2) + '\n')
            item['construction'] = target.relative_to(HERE).as_posix()
            item['construction_sha256'] = sha(target)
    out = HERE / 'current-execution-manifest.json'
    out.write_text(json.dumps(source, indent=2) + '\n')
    print(json.dumps({'cases': len(source['cases']),
                      'candidates': sum(1 + len(c['candidates']) for c in source['cases'])}))


if __name__ == '__main__':
    main()
