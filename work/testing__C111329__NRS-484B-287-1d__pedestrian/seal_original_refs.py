"""Create attempt-local source references after saved-only crossing processing."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

NAMES = ('site.json', 'native-acquisition.json', 'camera-manifest.json',
         'saved-receipt.json')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.attempt.resolve(strict=True)
    if args.output.exists() or not args.output.resolve().is_relative_to(root):
        raise ValueError('new source reference output must be within original attempt')
    refs = []
    for name in NAMES:
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('original source missing or outside attempt: ' + name)
        refs.append({'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    args.output.write_text(json.dumps(refs, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('sealed original source references:', ', '.join(NAMES))


if __name__ == '__main__':
    main()
