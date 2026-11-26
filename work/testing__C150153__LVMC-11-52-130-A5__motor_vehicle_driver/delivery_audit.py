"""Independent exact-case source and video audit for original delivery attempts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from independent_delivery_audit import audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('delivery audit output already exists')
    result = audit(args.attempt, args.packet, args.source_root,
                   diagnostic_fixture=args.diagnostic_fixture)
    if result['case_id'] != args.case:
        raise ValueError('independent delivery audit selected another exact case')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(args.case, 'full source and four-video decode passed')


if __name__ == '__main__':
    main()
