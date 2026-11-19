"""Keep the six 361-frame source specifications within the return size cap."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAP = 2 * 1024 * 1024


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    changed = 0
    for entry in manifest['cases']:
        recipe_ref = entry.get('fixture_recipe')
        if not recipe_ref:
            continue
        recipe_path = ROOT / recipe_ref
        recipe = json.loads(recipe_path.read_text())
        spec_path = ROOT / recipe['generator']['source']
        if spec_path.stat().st_size <= CAP:
            continue
        spec = json.loads(spec_path.read_text())
        compact = json.dumps(spec, separators=(',', ':'), ensure_ascii=False) + '\n'
        if len(compact.encode()) > CAP:
            raise ValueError('Diagnostic source still exceeds return cap: ' + str(spec_path))
        spec_path.write_text(compact)
        recipe['generator']['sha256'] = sha(spec_path)
        for source in recipe['sources']:
            if source['source'] == recipe['generator']['source']:
                source['sha256'] = sha(spec_path)
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
        changed += 1
        print(json.dumps({'case': entry['case_id'].removeprefix(HERE.name + '__'),
                          'bytes': spec_path.stat().st_size, 'sha256': sha(spec_path)}))
    if changed != 6:
        raise ValueError('Oversized short diagnostic count differs')
    print(json.dumps({'compacted': changed, 'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
