"""Materialize the first selected delivery bundle as the package root contract."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    selected = json.loads((ROOT / 'cases/marked_cross/delivery-construction.draft.json').read_text())
    for entry in selected['files']:
        path = ROOT / entry['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text() != entry['content']:
            if entry['path'] != 'runner.py':
                raise ValueError('selected source differs from existing package file: ' + entry['path'])
        path.write_text(entry['content'])
    (ROOT / 'construction.json').write_text(json.dumps(selected, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
