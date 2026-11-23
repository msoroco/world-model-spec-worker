"""Run the independent delivery audit on one synthetic diagnostic protocol."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from independent.delivery_audit import verify
from tests.test_delivery_audit import attempt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    suffix = args.case.rsplit("__", 1)[-1]
    private = REPO / ".runtime-work/c153046-delivery-contract"
    private.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=private) as temp:
        case_id = attempt(Path(temp) / suffix, suffix)
        if case_id != args.case:
            raise ValueError("diagnostic delivery case differs")
        receipt = verify(case_id, Path(temp) / suffix, allow_diagnostic=not args.strict)
        if receipt["physical_acceptance_claimed"]:
            raise AssertionError("synthetic protocol claimed physical acceptance")
        print(case_id, "diagnostic delivery protocol passed")


if __name__ == "__main__":
    main()
