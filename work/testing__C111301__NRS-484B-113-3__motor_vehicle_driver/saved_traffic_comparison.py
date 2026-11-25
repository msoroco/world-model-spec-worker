"""Compare two sealed original C111301 moving-traffic backing captures.

Both attempts retain their own source inventory and owner-release receipt.
The comparison checks the fixed traffic exposure and observed response; it does
not issue a statutory right-of-way verdict or assert participant visibility.
"""
import argparse
import json
from pathlib import Path

from original_source_audit import ASSIGNMENT, verify_seal
from traffic_measurements import compare
from traffic_saved import process

YIELD = ASSIGNMENT + "__traffic_yield"
CONTINUE = ASSIGNMENT + "__traffic_continue"


def audit(yield_attempt, continue_attempt, *, yield_owner_release_receipt=None,
          continue_owner_release_receipt=None, diagnostic_test=False):
    left_root = Path(yield_attempt).resolve()
    right_root = Path(continue_attempt).resolve()
    if left_root == right_root:
        raise ValueError("traffic comparison requires distinct original attempts")
    left_seal = verify_seal(left_root, diagnostic_test=diagnostic_test,
                            owner_release_receipt=yield_owner_release_receipt)
    right_seal = verify_seal(right_root, diagnostic_test=diagnostic_test,
                             owner_release_receipt=continue_owner_release_receipt)
    left = process(left_root, YIELD, allow_diagnostic=diagnostic_test)
    right = process(right_root, CONTINUE, allow_diagnostic=diagnostic_test)
    if left["source_id"] == right["source_id"]:
        raise ValueError("traffic comparison requires distinct source IDs")
    left_acq = json.loads((left_root / "acquisition.json").read_text(encoding="utf-8"))
    right_acq = json.loads((right_root / "acquisition.json").read_text(encoding="utf-8"))
    if left_acq["map_packet"]["sha256"] != right_acq["map_packet"]["sha256"]:
        raise ValueError("fixed original map, routes, blueprints or control differ")
    if [row["time_s"] for row in left["measurement"]["frames"]] != [row["time_s"] for row in right["measurement"]["frames"]]:
        raise ValueError("fixed original time window differs")
    measured = compare(left["measurement"], right["measurement"])
    return {"format": "saved-traffic-comparison-v1", "assignment_id": ASSIGNMENT,
            "comparison_id": "traffic_yield_response", "case_ids": [YIELD, CONTINUE],
            "attempt_acquisition_sha256": [left["acquisition_sha256"], right["acquisition_sha256"]],
            "capture_source_digests": [left_seal["source_digest"], right_seal["source_digest"]],
            "fixed_map_packet_sha256": left_acq["map_packet"]["sha256"],
            "source_ids": measured["sources"], "frame_count": left["frame_count"],
            "fixed_observables": measured["fixed_observables"] + ["time_s", "map_packet"],
            "changed_observables": measured["changed_observables"],
            "provenance_kind": "synthetic_fixture" if diagnostic_test else "native",
            "diagnostic_fixture": diagnostic_test, "physical_completion": False,
            "participant_visibility_confirmed": False, "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yield-attempt", required=True)
    parser.add_argument("--continue-attempt", required=True)
    parser.add_argument("--yield-owner-release-receipt")
    parser.add_argument("--continue-owner-release-receipt")
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic-test", action="store_true")
    args = parser.parse_args()
    result = audit(args.yield_attempt, args.continue_attempt,
                   yield_owner_release_receipt=args.yield_owner_release_receipt,
                   continue_owner_release_receipt=args.continue_owner_release_receipt,
                   diagnostic_test=args.diagnostic_test)
    output = Path(args.output).resolve()
    if any(output == root or root in output.parents for root in
           (Path(args.yield_attempt).resolve(), Path(args.continue_attempt).resolve())):
        raise ValueError("comparison receipt must be written outside original attempts")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("saved traffic comparison passed for", YIELD, CONTINUE)


if __name__ == "__main__":
    main()
