"""Bind the four current selected offline checks; no readiness claim."""
import hashlib
import json
from pathlib import Path

from build_selected import CASES

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = PACKAGE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for suffix, entry in zip(CASES, manifest['cases']):
        source = ROOT / '.runtime-work' / 'c245490-owner' / ('offline-v3-' + suffix) / 'offline.log'
        if not source.is_file() or 'OK' not in source.read_text():
            raise ValueError('Current exact offline check missing: ' + suffix)
        log = PACKAGE / 'offline' / (suffix + '-primary.log')
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('\n'.join(line.rstrip() for line in source.read_text().splitlines()).rstrip() + '\n')
        entry['offline'] = {
            'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + PACKAGE.name +
                       '/execution-manifest.json --case ' + entry['case_id'] +
                       ' --output .runtime-work/c245490-owner/offline-v3-' + suffix,
            'exit_code': 0,
            'construction_sha256': entry['construction_sha256'],
            'log': str(log.relative_to(PACKAGE)),
            'log_sha256': sha(log),
        }
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'offline_bound': len(manifest['cases']), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
