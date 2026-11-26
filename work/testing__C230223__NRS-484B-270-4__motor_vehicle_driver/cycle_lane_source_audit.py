"""Independent saved attempt audit using externally reviewed source hashes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cycle_lane_delivery import audit_delivery


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    review = json.loads(Path(args.review).read_text(encoding="utf-8"))
    reviewed = review.get("reviews", {}).get(args.case)
    if not isinstance(reviewed, dict) or set(reviewed) != {"site", "subsection_3", "vehicle"}:
        raise ValueError("independent site, subsection 3 and vehicle review hashes required")
    expected_attempt = review.get("attempts", {}).get(args.case)
    if not expected_attempt or Path(expected_attempt).resolve() != Path(args.attempt).resolve():
        raise ValueError("reviewed original attempt path mismatch")
    result = audit_delivery(args.attempt, reviewed["site"], reviewed["subsection_3"],
                            reviewed["vehicle"])
    result["physical_acceptance_claimed"] = False
    result["legal_verdict"] = None
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"case_id": args.case, "source_audit_written": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
