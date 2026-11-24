"""Select current-runtime exception-vehicle CPU constructions and strict sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRANCH = HERE / 'exception'
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update(content, path):
    changes = [('source-scope.json', 'context-scope.json'),
               ('front_lamp.mkv', 'approach.mkv'),
               ('rear_approach.mkv', 'reference_corner.mkv'),
               ('officer_reference.mkv', 'driver_reference.mkv'),
               ("'front_lamp'", "'approach'"),
               ("'rear_approach'", "'reference_corner'"),
               ("'officer_reference'", "'driver_reference'"),
               ('"front_lamp"', '"approach"'),
               ('"rear_approach"', '"reference_corner"'),
               ('"officer_reference"', '"driver_reference"')]
    for old, new in changes:
        content = content.replace(old, new)
    if path == 'candidates.py':
        start = content.index("            {'name': 'subject_reference',")
        end = content.index("            {'name': 'driver_reference',", start)
        content = content[:start] + content[end:]
    if path == 'runner.py':
        content = content.replace("len(plan['camera_plan']) == 5", "len(plan['camera_plan']) == 4")
        content = content.replace("'reference_corner', 'subject_reference', 'driver_reference'", "'reference_corner', 'driver_reference'")
        content = content.replace("(1280, 720), (1280, 720), (1280, 720), (1280, 720)]", "(1280, 720), (1280, 720), (1280, 720)]")
        content = content.replace("'camera_count': 5", "'camera_count': 4")
    if path == 'finalize.py':
        content = content.replace("'subject_reference.mkv', 'driver_reference.mkv'", "'driver_reference.mkv'")
    if path == 'tests/test_construction.py':
        content = content.replace("result['camera_count'], 5", "result['camera_count'], 4")
    if path == 'config.json':
        config = json.loads(content)
        config['cameras'] = [x for x in config['cameras'] if x['name'] != 'subject_reference']
        content = json.dumps(config, indent=2) + '\n'
    return content


def main():
    m = json.loads((BRANCH / 'package-manifest.json').read_text())
    m['runtime_manifest_sha256'] = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    m['status'] = 'selected_diagnostic_construction'
    for case in m['cases']:
        suffix = case['case_id'].rsplit('__', 1)[1]
        contract = json.loads((BRANCH / case['measurement_contract']).read_text())
        contract['format'] = 'worker-measurement-contract'
        for row in contract['requirements']:
            row['inputs'] = [x.replace('source-scope.json', 'context-scope.json') for x in row['inputs']]
        contract['negative']['remove'] = ['context-scope.json']
        contract['negative']['error_contains'] = 'Missing required source: context-scope.json'
        cpath = HERE / 'current-exception-contracts' / (suffix + '.json')
        cpath.parent.mkdir(exist_ok=True)
        cpath.write_text(json.dumps(contract, indent=2) + '\n')
        case['measurement_contract'] = cpath.relative_to(HERE).as_posix()
        case['fixture_recipe'] = f'work/{HERE.name}/current-{suffix}-recipe.json'
        for candidate in ('primary', 'fallback1', 'fallback2'):
            item = case if candidate == 'primary' else next(x for x in case['candidates'] if x['id'] == candidate)
            path = BRANCH / item['construction']
            data = json.loads(path.read_text())
            for f in data['files']:
                modified = update(f['content'], f['path'])
                if modified != f['content']:
                    f['content'] = modified
                    f.pop('source', None)
            target = HERE / 'current-exception-bundles' / suffix / candidate / 'construction.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(data, indent=2) + '\n')
            item['construction'] = target.relative_to(HERE).as_posix()
            item['construction_sha256'] = sha(target)
        case['candidates'] = [x for x in case['candidates'] if x['id'] in ('fallback1', 'fallback2')]
        case['kind'] = 'delivery'
    (HERE / 'current-exception-manifest.json').write_text(json.dumps(m, indent=2) + '\n')
    print(json.dumps({'selected': 6, 'manifest_sha256': sha(HERE / 'current-exception-manifest.json')}))


if __name__ == '__main__':
    main()
