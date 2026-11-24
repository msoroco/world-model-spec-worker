"""Keep current v2 fallback constructions separate from primary receipts."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = json.loads((HERE / 'draft-execution-manifest.json').read_text())
OUT = HERE / 'v2-fallbacks'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for case in ('witness_1', 'witness_2'):
        manifest = copy.deepcopy(json.loads((HERE / ('v2-primary-' + case + '-manifest.json')).read_text()))
        entry = manifest['cases'][0]
        original_entry = next(row for row in SOURCE['cases'] if row['case_id'] == entry['case_id'])
        candidates = []
        for old in original_entry['candidates']:
            candidate = copy.deepcopy(old)
            construction = json.loads((HERE / old['construction']).read_text())
            finalizer = next(item for item in construction['files'] if item['path'] == 'finalize.py')
            needle = 'from measure import measure\n'
            assert finalizer['content'].count(needle) == 1
            finalizer['content'] = finalizer['content'].replace(needle,
                'from measure import measure as _measure\n\n\n'
                'def measure(*args, **kwargs):\n'
                '    return _measure(*args, **kwargs)\n')
            path = OUT / case / candidate['id'] / 'construction.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(construction, indent=2) + '\n')
            candidate['construction'] = str(path.relative_to(HERE))
            candidate['construction_sha256'] = sha(path)
            candidates.append(candidate)
        assert len(candidates) == 3
        entry['candidates'] = candidates
        manifest['status'] = 'unselected_current_v2_cpu_fallback_proof'
        path = HERE / ('v2-fallbacks-' + case + '-manifest.json')
        path.write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({'case': case, 'fallbacks': 3, 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
