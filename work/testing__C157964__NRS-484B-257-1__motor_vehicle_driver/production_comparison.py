"""Audit an original C157964 comparison after both Native attempts close."""

import argparse
import json
from pathlib import Path

from comparison_audit import audit_pair


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--first-attempt", required=True, type=Path)
    parser.add_argument("--second-attempt", required=True, type=Path)
    parser.add_argument("--first-site-sha256", required=True)
    parser.add_argument("--second-site-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("comparison output already exists")
    report = audit_pair(
        args.comparison_id,
        args.first_attempt,
        args.second_attempt,
        expected_site_hashes=(args.first_site_sha256, args.second_site_sha256),
    )
    if report["diagnostic_fixture"] is not False or report["source_integrity"] is not True:
        raise ValueError("original comparison source integrity failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"comparison_id": args.comparison_id, "source_integrity": True}, sort_keys=True))


if __name__ == "__main__":
    main()
