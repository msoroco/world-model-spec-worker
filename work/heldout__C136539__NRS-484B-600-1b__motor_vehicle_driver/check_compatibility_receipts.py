"""Verify the current slow-person exact compatibility receipt."""

import json
from pathlib import Path

from worker_exchange.package_compatibility import check_receipts


def main():
    root = Path(__file__).resolve().parent
    repo = root.parents[1]
    manifest = json.loads((root / 'probe-compatibility-manifest.json').read_text())
    print('exact receipt check', check_receipts(repo, root, manifest))


if __name__ == '__main__':
    main()
