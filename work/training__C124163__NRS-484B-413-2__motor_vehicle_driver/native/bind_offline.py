"""Bind current-runtime exact offline proofs to the selected manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = ROOT/'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1'):
            source = REPO/'.runtime-work'/f'c124163-offline-{condition}-{candidate}-v7'/'offline.log'
            if not source.exists() or 'Ran 2 tests' not in source.read_text() or 'OK' not in source.read_text():
                raise ValueError('Exact offline proof missing: '+condition+' '+candidate)
            dest = ROOT/'proofs'/condition/candidate/'offline.log'
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(source.read_text().rstrip()+'\n')
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            selected['offline'] = {'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                            'work/'+ROOT.name+'/execution-manifest.json --case '
                            +entry['case_id']+' --candidate '+candidate+' --output '
                            f'.runtime-work/c124163-offline-{condition}-{candidate}-v7',
                            'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
                            'log': str(dest.relative_to(ROOT)), 'log_sha256': sha(dest)}
        entry['fixture_recipe'] = f'work/{ROOT.name}/diagnostic-{condition}-primary-recipe.json'
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'offline_bound': len(manifest['cases']), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
