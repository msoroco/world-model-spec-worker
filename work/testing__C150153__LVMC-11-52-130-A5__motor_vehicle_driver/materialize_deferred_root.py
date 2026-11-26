"""Expose the first exact selected bundle at canonical assignment root paths."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'execution-manifest.json'


def materialize() -> None:
    manifest = json.loads(MANIFEST.read_text())
    entry = manifest['cases'][0]
    construction_path = HERE / entry['construction']
    content = construction_path.read_text()
    construction = json.loads(content)
    if construction['case_id'] != entry['case_id']:
        raise ValueError('root materialization selected another case')
    root_construction = HERE / 'construction.json'
    if root_construction.exists() and root_construction.read_text() != content:
        raise ValueError('refusing to overwrite another root construction')
    for item in construction['files']:
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_text() != item['content']:
                raise ValueError('root source differs from selected construction: ' + item['path'])
        else:
            target.write_text(item['content'])
    if not root_construction.exists():
        root_construction.write_text(content)
    print(entry['case_id'], 'canonical root bundle materialized')


if __name__ == '__main__':
    materialize()
