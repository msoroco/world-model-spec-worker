"""Refresh the eight inline source snapshots after a reviewed CPU code change."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
SOURCES = {'runner.py': 'runner.py', 'parking.py': 'parking.py',
           'finalizer.py': 'finalizer.py',
           'saved_media_audit.py': 'saved_media_audit.py',
           'tests/test_parking.py': 'tests/test_parking.py'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    manifest_path = FOLDER / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        path = FOLDER / entry['construction']
        construction = json.loads(path.read_text())
        files = {item['path']: item for item in construction['files']}
        for package_path, local_path in SOURCES.items():
            source = FOLDER / local_path
            files[package_path] = {'path': package_path,
                                   'source': str(source.relative_to(ROOT)),
                                   'content': source.read_text()}
        construction['files'] = list(files.values())
        path.write_text(json.dumps(construction, indent=2) + '\n')
        entry['construction_sha256'] = sha(path)
        entry['offline']['construction_sha256'] = sha(path)
        entry['offline']['exit_code'] = -1
        entry['offline']['scope'] = 'CPU materialization pending refreshed full-media finalizer'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    return len(manifest['cases'])


if __name__ == '__main__':
    print(build())
