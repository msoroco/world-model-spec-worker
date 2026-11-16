"""Build disjoint candidate bundles with an identical nested draft file inventory."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    old = HERE / 'native/package-selected-current-input'
    new = HERE / 'native/package-selected-inventory-v2'
    for case in CASES:
        bundles = {candidate: json.loads((old / case / candidate / 'construction.json').read_text())
                   for candidate in CANDIDATES}
        nested = {}
        for bundle in bundles.values():
            for item in bundle['files']:
                path = item['path']
                if '/drafts/' + case + '/' in path:
                    if path in nested and nested[path] != item:
                        raise ValueError('Candidate nested draft source differs: ' + path)
                    nested[path] = item
        if len(nested) < 16 or any(not any('/' + c + '/' in path for path in nested)
                                   for c in CANDIDATES):
            raise ValueError(f'Incomplete candidate nested draft inventory: {len(nested)}')
        entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
        for candidate, bundle in bundles.items():
            paths = {item['path'] for item in bundle['files']}
            bundle['files'].extend(item for path, item in sorted(nested.items()) if path not in paths)
            output = new / case / candidate / 'construction.json'
            write(output, bundle)
            ref = entry if candidate == 'primary' else next(x for x in entry['candidates'] if x['id'] == candidate)
            ref['construction'] = str(output.relative_to(HERE))
            ref['construction_sha256'] = sha(output)
            ref.pop('offline', None)
            ref.pop('compatibility', None)
        for key in ('offline', 'compatibility', 'negative', 'physical_preparation'):
            entry.pop(key, None)
    manifest['status'] = 'inventory_v2_requires_current_runtime_reproof'
    path = HERE / 'update045-execution-manifest.json'
    write(path, manifest)
    print(json.dumps({'candidate_count': 16, 'manifest': path.name,
                      'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
