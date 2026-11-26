"""Run saved original delivery or controlled comparison audit after owner release."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from comparison_audit import PAIRS, audit as compare
from delivery_audit import audit as deliver


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--case")
    parser.add_argument("--comparison", choices=tuple(PAIRS))
    parser.add_argument("--receipts", type=Path)
    args = parser.parse_args()
    root = args.authority_root.resolve()
    if args.receipt and args.case and not args.comparison and not args.receipts:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        if receipt.get("case_id") != args.case:
            raise ValueError("exact case receipt differs")
        result = deliver(root, receipt)
    elif args.comparison and args.receipts and not args.receipt and not args.case:
        sources = json.loads(args.receipts.read_text(encoding="utf-8"))
        if set(sources) != {"left_audit", "right_audit"}:
            raise ValueError("exact comparison audit paths required")
        site = json.loads((root / "site.json").read_text(encoding="utf-8"))
        left, right, _ = PAIRS[args.comparison]
        audits = [json.loads((root / sources[key]).read_text(encoding="utf-8"))
                  for key in ("left_audit", "right_audit")]
        result = compare(args.comparison, site["scenes"][left], site["scenes"][right], *audits)
    else:
        raise ValueError("choose one exact delivery or comparison audit")
    if args.output.exists():
        raise ValueError("fresh audit output required")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
