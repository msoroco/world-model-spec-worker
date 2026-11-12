"""Rebind every exact inline construction after sight-route implementation edits."""

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'execution-manifest.json'
SOURCES = {name: (HERE / name).read_text()
           for name in ('runner.py', 'u_turn_construction.py',
                        'tests/test_u_turn_construction.py')}


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def update(source):
    path = HERE / source
    construction = json.loads(path.read_text())
    found = set()
    for item in construction['files']:
        if item['path'] in SOURCES:
            item['content'] = SOURCES[item['path']]
            found.add(item['path'])
    if found != set(SOURCES):
        raise ValueError('Exact construction omits affected source: ' + source)
    path.write_text(json.dumps(construction, indent=2) + '\n')
    return digest(path)


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        entry['construction_sha256'] = update(entry['construction'])
        for key in ('offline', 'compatibility', 'negative', 'delivery_acceptance',
                    'physical_preparation'):
            entry.pop(key, None)
        for candidate in entry['candidates']:
            candidate['construction_sha256'] = update(candidate['construction'])
            for key in ('offline', 'compatibility'):
                candidate.pop(key, None)
        print(entry['case_id'], 'sources rebound')
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
