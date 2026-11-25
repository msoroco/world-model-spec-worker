"""Compare source-sealed Native rail-stop attempts after independent audits."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt", action="append", required=True, type=Path)
    args = parser.parse_args()
    plan = json.loads((HERE / "case-plan.json").read_text())
    selected = [row for row in plan["comparisons"] if row["comparison_id"] == args.comparison]
    if len(selected) != 1 or len(args.attempt) != len(selected[0]["case_ids"]):
        raise ValueError("exact comparison and all member attempts required")
    comparison = selected[0]
    audited = [audit(path) for path in args.attempt]
    if [row["case_id"] for row in audited] != comparison["case_ids"]:
        raise ValueError("comparison attempt identity differs")
    for name in ("native-crossing-geometry.json", "native-authority-record.json",
                 "native-stop-device.json"):
        if len({sha(path / name) for path in args.attempt}) != 1:
            raise ValueError("fixed crossing source differs: " + name)
    configs = [json.loads((path / "config.json").read_text()) for path in args.attempt]
    if len({json.dumps(row["cameras"], sort_keys=True) for row in configs}) != 1:
        raise ValueError("fixed camera plan differs")
    observations = [row["nearest_rail_measurement"] for row in audited]
    field = {"lower_15_ft": "first_stop_body_to_nearest_rail_min_ft",
             "upper_50_ft": "first_stop_body_to_nearest_rail_min_ft",
             "cessation": "complete_stop_observed",
             "subsequent_care": "conflict_actor_present"}[args.comparison]
    values = [row.get(field) for row in observations]
    if any(value is None for value in values) or len(set(values)) != len(values):
        raise ValueError("declared original measurement contrast missing")
    print(json.dumps({"comparison_id": args.comparison, "case_ids": comparison["case_ids"],
                      "field": field, "values": values,
                      "native_delivery_audits_passed": True,
                      "legal_judgment": "unresolved"}, separators=(",", ":")))


if __name__ == "__main__":
    main()
