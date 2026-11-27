"""Independent exact stop-sign original packet and paired-motion audit CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stop_view_measurement import compare_original, inspect_original


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path)
    parser.add_argument("--case")
    parser.add_argument("--left", type=Path)
    parser.add_argument("--right", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.original and args.case and not args.left and not args.right:
        result = inspect_original(args.original, args.case)
    elif args.left and args.right and not args.original and not args.case:
        result = compare_original(args.left, args.right)
    else:
        raise ValueError("select one original packet or one exact packet pair")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
