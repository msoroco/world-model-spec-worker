"""Require an independent source audit to report the queued exact case."""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    report = json.load(sys.stdin)
    if report.get("case_id") != args.case:
        raise SystemExit("source audit reported another case")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
