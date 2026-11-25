"""Production pedestrian comparison bound to both sealed Native captures."""
import argparse
import json
from pathlib import Path

from original_source_audit import verify_seal
from saved_comparison import audit as compare_saved


def audit(yield_attempt, continue_attempt, *, yield_owner_release_receipt,
          continue_owner_release_receipt):
    left = Path(yield_attempt).resolve()
    right = Path(continue_attempt).resolve()
    if left == right:
        raise ValueError("pedestrian comparison requires distinct original attempts")
    left_seal = verify_seal(left, owner_release_receipt=yield_owner_release_receipt)
    right_seal = verify_seal(right, owner_release_receipt=continue_owner_release_receipt)
    result = compare_saved(left, right)
    result["capture_source_digests"] = [left_seal["source_digest"], right_seal["source_digest"]]
    result["provenance_kind"] = "native"
    result["diagnostic_fixture"] = False
    result["participant_visibility_confirmed"] = False
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yield-attempt", required=True)
    parser.add_argument("--continue-attempt", required=True)
    parser.add_argument("--yield-owner-release-receipt", required=True)
    parser.add_argument("--continue-owner-release-receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if any(output == root or root in output.parents for root in
           (Path(args.yield_attempt).resolve(), Path(args.continue_attempt).resolve())):
        raise ValueError("comparison receipt must be written outside original attempts")
    result = audit(args.yield_attempt, args.continue_attempt,
                   yield_owner_release_receipt=args.yield_owner_release_receipt,
                   continue_owner_release_receipt=args.continue_owner_release_receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("sealed pedestrian comparison passed")


if __name__ == "__main__":
    main()
