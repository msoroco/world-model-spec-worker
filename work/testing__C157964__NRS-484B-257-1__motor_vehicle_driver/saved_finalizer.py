"""Recorded-only C157964 attempt finalization; original sources stay untouched."""

import argparse
import json
from pathlib import Path

from saved_audit import audit_saved
from yield_view import CASES, require


def finalize(attempt, output, case, *, allow_diagnostic=False,
             expected_site_packet_sha256=None):
    audit = audit_saved(attempt, case, allow_diagnostic=allow_diagnostic,
                        expected_site_packet_sha256=expected_site_packet_sha256)
    target = Path(output)
    require(not target.exists(), "saved finalization output already exists")
    measurement = json.loads((Path(attempt) / "measurement.json").read_text())
    result = {
        "format": "c157964-recorded-only-finalization-v1",
        "case_id": case.case_id,
        "source_audit": audit,
        "measurements": measurement,
        "diagnostic_fixture": audit["diagnostic_fixture"],
        "original_attempt_modified": False,
        "physical_acceptance_claimed": False,
        "legal_judgment": None,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--allow-diagnostic", action="store_true")
    parser.add_argument("--expected-site-packet-sha256")
    args = parser.parse_args()
    case = next((item for item in CASES if item.case_id == args.case), None)
    require(case is not None, "unknown exact yield case")
    print(json.dumps(finalize(args.attempt, args.output, case,
                              allow_diagnostic=args.allow_diagnostic,
                              expected_site_packet_sha256=args.expected_site_packet_sha256),
                     sort_keys=True))


if __name__ == "__main__":
    main()
