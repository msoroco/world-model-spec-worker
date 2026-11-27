"""Independent controlled comparison entrypoint for saved local attempts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_comparisons import PAIRS, compare


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=tuple(PAIRS), required=True)
    parser.add_argument("--first-attempt", type=Path, required=True)
    parser.add_argument("--second-attempt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.comparison, args.first_attempt,
                             args.second_attempt), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
