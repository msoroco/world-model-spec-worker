"""Select current-runtime witness candidates with canonical four cameras and staged scope."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update(content):
    replacements = [('source-scope.json', 'context-scope.json'),
                    ('front_lamp.mkv', 'approach.mkv'),
                    ('rear_approach.mkv', 'reference_corner.mkv'),
                    ('subject_reference.mkv', 'driver_reference.mkv'),
                    ("'front_lamp', 'rear_approach', 'subject_reference'", "'approach', 'reference_corner', 'driver_reference'"),
                    ("spec['name'] == 'front_lamp'", "spec['name'] == 'approach'"),
                    ("'name': 'front_lamp'", "'name': 'approach'"),
                    ("'name': 'rear_approach'", "'name': 'reference_corner'"),
                    ("'name': 'subject_reference'", "'name': 'driver_reference'"),
                    ('"name": "front_lamp"', '"name": "approach"'),
                    ('"name": "rear_approach"', '"name": "reference_corner"'),
                    ('"name": "subject_reference"', '"name": "driver_reference"')]
    for old, new in replacements:
        content = content.replace(old, new)
    return content


def main():
    m = json.loads((HERE / 'current-witness-manifest.json').read_text())
    for case in m['cases']:
        suffix = case['case_id'].rsplit('__', 1)[1]
        for candidate in ('primary', 'fallback1', 'fallback2'):
            item = case if candidate == 'primary' else next(x for x in case['candidates'] if x['id'] == candidate)
            source = HERE / item['construction']
            d = json.loads(source.read_text())
            for f in d['files']:
                changed = update(f['content'])
                if changed != f['content']:
                    f['content'] = changed
                    f.pop('source', None)
            destination = HERE / 'current-witness-bundles' / suffix / candidate / 'construction.json'
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(d, indent=2) + '\n')
            item['construction'] = destination.relative_to(HERE).as_posix()
            item['construction_sha256'] = sha(destination)
        case['candidates'] = [x for x in case['candidates'] if x['id'] in ('fallback1', 'fallback2')]
        case['kind'] = 'delivery'
    m['status'] = 'selected_diagnostic_construction'
    (HERE / 'current-witness-manifest.json').write_text(json.dumps(m, indent=2) + '\n')
    for suffix in ('witness_1', 'witness_2'):
        contract = HERE / 'current-witness-contracts' / (suffix + '.json')
        d = json.loads(contract.read_text())
        for row in d['requirements']:
            row['inputs'] = [x.replace('source-scope.json', 'context-scope.json') for x in row['inputs']]
        d['negative']['remove'] = ['context-scope.json']
        d['negative']['error_contains'] = 'Missing required source: context-scope.json'
        contract.write_text(json.dumps(d, indent=2) + '\n')
    return {'manifest_sha256': sha(HERE / 'current-witness-manifest.json'), 'selected': 6}


if __name__ == '__main__':
    print(json.dumps(main()))
