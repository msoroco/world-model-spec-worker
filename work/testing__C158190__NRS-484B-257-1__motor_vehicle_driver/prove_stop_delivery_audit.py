"""Reproduce the labeled synthetic CPU audit and original-source rejection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stop_delivery_audit import audit
from stop_saved_finalizer import finalize
from stop_sign_branch import CASES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id", choices=tuple(CASES))
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    suffix = args.case_id.removeprefix(root.name + "__")
    folder = root / "cases" / suffix
    if args.negative:
        try:
            finalize(args.case_id, folder / "diagnostic-sources")
        except (ValueError, FileNotFoundError) as error:
            raise ValueError("original saved acquisition required for physical review") from error
        raise ValueError("diagnostic source was accepted as original")
    value = audit(args.case_id, folder / "diagnostic-sources",
                  folder / "saved-processing-proof.json")
    if value["physical_acceptance"] != "unverified" or value["legal_acceptance"] is not None:
        raise ValueError("diagnostic audit overclaims physical or legal acceptance")
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
