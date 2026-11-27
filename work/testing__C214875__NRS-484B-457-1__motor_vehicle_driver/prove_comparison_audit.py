"""Source-bound comparison probes for the exact right-curb cases."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from audit_comparisons import PAIRS, compare


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=tuple(PAIRS), required=True)
    parser.add_argument("--mode", choices=("diagnostic-positive", "source-negative"), required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    scratch = root / ".runtime-work"
    a, b = PAIRS[args.comparison]
    first = scratch / ("c214875-saved-" + a + "-v3-attempt")
    second = scratch / ("c214875-saved-" + b + "-v3-attempt")
    if args.mode == "diagnostic-positive":
        result = compare(args.comparison, first, second)
        if result["physical_acceptance"] or not result["fixed_source_and_capture_checked"]:
            raise ValueError("diagnostic comparison gained physical acceptance")
        print(json.dumps(result, sort_keys=True))
        return
    with tempfile.TemporaryDirectory(prefix="c214875-comp-tamper-", dir=scratch) as name:
        copy = Path(name) / "attempt"
        shutil.copytree(second, copy)
        site = copy / "original-attempt/site.json"
        data = json.loads(site.read_text())
        data["reviewed_assertions"]["residence_district"] = False
        site.write_text(json.dumps(data, sort_keys=True) + "\n")
        compare(args.comparison, first, copy)
        raise ValueError("tampered fixed source was accepted")


if __name__ == "__main__":
    main()
