"""Exact saved-attempt CLI for the two red-X comparison audits."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import PAIRS, audit_pair


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-id", required=True, choices=tuple(PAIRS))
    parser.add_argument("--baseline-attempt", type=Path, required=True)
    parser.add_argument("--changed-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    if args.baseline_attempt.resolve() == args.changed_attempt.resolve():
        raise ValueError("comparison reuses one original attempt")
    receipt = audit_pair(args.comparison_id, args.baseline_attempt,
                         args.changed_attempt, diagnostic=args.diagnostic)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(args.comparison_id + ": exact red-X comparison audit passed")


if __name__ == "__main__":
    main()
