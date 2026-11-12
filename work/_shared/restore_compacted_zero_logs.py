"""Restore source-hashed empty diagnostic logs from the return inventory."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


def restore(assignment):
    root = Path(__file__).resolve().parents[2]
    inventory = json.loads((root / 'work/_shared/prune-history.json').read_text())
    prefix = f'work/{assignment}/'
    count = 0
    for row in inventory.get('compacted_zero_logs', []):
        rel = row['path']
        if not rel.startswith(prefix):
            continue
        path = root / rel
        if path.exists():
            raise ValueError(f'Refusing to overwrite restored log: {rel}')
        if row['text'] != '' or row['sha256'] != sha256(b'').hexdigest():
            raise ValueError(f'Invalid compacted empty log: {rel}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'')
        count += 1
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--assignment', required=True)
    args = parser.parse_args()
    print(restore(args.assignment))
