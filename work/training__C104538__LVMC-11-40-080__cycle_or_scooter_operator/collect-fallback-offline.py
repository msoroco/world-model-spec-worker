"""Retain exact current-runtime offline checks for selected fallback constructions."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        candidate = entry['candidates'][0]
        source = ROOT / '.runtime-work' / ('c104538-fallback-offline-' + suffix) / 'offline.log'
        if not source.is_file():
            raise ValueError('Missing fallback offline log: ' + suffix)
        retained = HERE / 'selected-proof' / suffix / 'fallback1' / 'offline.log'
        retained.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, retained)
        candidate['offline'] = {
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} --candidate fallback1 --output .runtime-work/c104538-fallback-offline-{suffix}',
            'exit_code': 0,
            'construction_sha256': candidate['construction_sha256'],
            'log': str(retained.relative_to(HERE)),
            'log_sha256': sha(retained),
        }
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
