"""Rebuild all selected bundles with fresh saved-source finalization."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    finalizer = (HERE / 'native/finalize_selected.py').read_text()
    changed = 0
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        for candidate in [entry, *entry['candidates']]:
            name = candidate.get('id', 'primary')
            source = HERE / candidate['construction']
            construction = json.loads(source.read_text())
            files = [item for item in construction['files'] if item['path'] == 'finalize_selected.py']
            if len(files) != 1 or 'prepared=attempt/\'prepared-sources\'' not in files[0]['content']:
                raise ValueError('Selected finalizer source differs')
            files[0]['content'] = finalizer
            target = HERE / 'update803-constructions' / suffix / name / 'construction.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise FileExistsError(target)
            target.write_text(json.dumps(construction, indent=2) + '\n')
            candidate['construction'] = target.relative_to(HERE).as_posix()
            candidate['construction_sha256'] = sha(target)
            changed += 1
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'constructions': changed,
                      'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    main()
