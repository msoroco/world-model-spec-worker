"""Bind the four current source recipes to the existing exact constructions."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    batches = [json.loads((HERE / name).read_text()) for name in (
        'draft-execution-manifest.json',
        'draft-exception-execution-manifest.json',
    )]
    active = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    if any(batch['runtime_manifest_sha256'] != active for batch in batches):
        raise ValueError('Draft construction binds another runtime')
    entries = []
    for batch in batches:
        for source in batch['cases']:
            entry = copy.deepcopy(source)
            suffix = entry['case_id'][len(HERE.name) + 2:]
            entry['kind'] = 'delivery'
            entry['fixture_recipe'] = 'work/' + HERE.name + '/current-' + suffix + '-recipe.json'
            entry['measurement_contract'] = 'current-contracts/' + suffix + '.json'
            entry['candidates'] = [candidate for candidate in entry['candidates']
                                   if candidate['id'] in ('fallback1', 'fallback2')]
            if not (ROOT / entry['fixture_recipe']).is_file():
                raise ValueError('Missing current recipe for ' + suffix)
            entries.append(entry)
    manifest = {
        'format': 'worker-execution-manifest',
        'assignment_id': HERE.name,
        'runtime_manifest_sha256': active,
        'status': 'delivery_prepared',
        'delivery_ready': False,
        'original_native_observed': False,
        'cases': entries,
    }
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(entries), 'candidates': sum(len(e['candidates']) + 1 for e in entries),
                      'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
