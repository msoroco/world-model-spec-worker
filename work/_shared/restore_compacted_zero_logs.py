"""Restore source-hashed compacted diagnostic logs from the return inventory."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


def restore(assignment, skip_existing_verified=False):
    root = Path(__file__).resolve().parents[2]
    inventories = [json.loads(path.read_text()) for path in
                   sorted((root / 'work/_shared').glob('prune-history*.json'))]
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
            if skip_existing_verified and sha256(path.read_bytes()).hexdigest() == row['sha256']:
                continue
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
    parser.add_argument('--skip-existing-verified', action='store_true')
    args = parser.parse_args()
    print(restore(args.assignment, args.skip_existing_verified))
