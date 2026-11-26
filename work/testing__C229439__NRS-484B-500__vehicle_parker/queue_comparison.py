"""Run an exact comparison on saved original analysis roots after delivery."""

import argparse
import json
from pathlib import Path

from comparison_audit import COMPARISONS, audit_saved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", choices=COMPARISONS, required=True)
    parser.add_argument("--analysis", action="append", nargs=2,
                        metavar=("CASE_SUFFIX", "SAVED_ANALYSIS"), required=True)
    parser.add_argument("--scratch", required=True)
    args = parser.parse_args(argv)
    roots = dict(args.analysis)
    if len(roots) != len(args.analysis):
        raise ValueError("duplicate exact comparison case")
    scratch = Path(args.scratch).resolve()
    if not scratch.is_dir():
        raise ValueError("comparison scratch directory missing")
    result = audit_saved(args.comparison, roots, scratch)
    if result["fixture_only"]:
        raise ValueError("diagnostic fixture cannot satisfy delivered comparison")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
