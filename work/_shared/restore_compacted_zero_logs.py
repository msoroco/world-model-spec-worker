"""Restore source-hashed compacted diagnostic logs from the return inventory."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


def restore(assignment):
    root = Path(__file__).resolve().parents[2]
    inventory = json.loads((root / 'work/_shared/prune-history.json').read_text())
    prefix = f'work/{assignment}/'
    count = 0
    rows = (inventory.get('compacted_zero_logs', []) +
            inventory.get('compacted_text_files', []))
    for row in rows:
        rel = row['path']
        if not rel.startswith(prefix):
            continue
        path = root / rel
        if path.exists():
            raise ValueError(f'Refusing to overwrite restored log: {rel}')
        data = row['text'].encode('utf-8')
        if row['sha256'] != sha256(data).hexdigest():
            raise ValueError(f'Invalid compacted log: {rel}')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        count += 1
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--assignment', required=True)
    args = parser.parse_args()
    print(restore(args.assignment))
