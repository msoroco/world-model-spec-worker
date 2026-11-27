"""Exercise exact saved curb delivery audits without claiming physical evidence."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from delivery_audit import audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--mode", choices=("diagnostic-positive", "source-negative"), required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    if args.case != folder.name + "__" + args.variant:
        raise ValueError("case identity differs from selected curb variant")
    repo = folder.parent.parent
    scratch = repo / ".runtime-work"
    attempt = scratch / ("c214875-saved-" + args.variant + "-v3-attempt")
    version = scratch / ("c214875-saved-" + args.variant + "-v3-out/v0001")
    processing = version / "processing.json"
    decode = version / "final-decode.json"
    if args.mode == "diagnostic-positive":
        result = audit(attempt, processing, decode, args.case)
        if not result["auditor_passed"] or result["accepted_for_local_review"]:
            raise ValueError("diagnostic curb evidence gained physical acceptance")
        print(json.dumps(result, sort_keys=True))
        return
    with tempfile.TemporaryDirectory(prefix="c214875-tamper-", dir=scratch) as name:
        copy = Path(name) / "attempt"
        shutil.copytree(attempt, copy)
        wheel = copy / "original-attempt/wheel-motion.jsonl"
        wheel.write_text(wheel.read_text() + "tamper\n")
        audit(copy, processing, decode, args.case)
        raise ValueError("tampered original curb source was accepted")


if __name__ == "__main__":
    main()
