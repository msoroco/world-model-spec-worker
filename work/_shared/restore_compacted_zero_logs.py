"""Restore source-hashed compacted diagnostic logs from the return inventory."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


def restore(assignment):
    root = Path(__file__).resolve().parents[2]
    inventories = [json.loads((root / name).read_text()) for name in
                   ('work/_shared/prune-history.json',
                    'work/_shared/prune-history-2.json',
                    'work/_shared/prune-history-3.json',
                    'work/_shared/prune-history-4.json',
                    'work/_shared/prune-history-5.json')]
    prefix = f'work/{assignment}/'
    count = 0
    rows = [row for inventory in inventories for row in
            inventory.get('compacted_zero_logs', []) +
            inventory.get('compacted_text_files', [])]
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
