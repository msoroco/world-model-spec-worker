"""Measure three synthetic body-reference outcomes for an exact yield case."""

import argparse
import hashlib
import json
from pathlib import Path

from yield_view import CASES, require


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate(attempt, case, kind):
    attempt = Path(attempt).resolve()
    site_path = attempt / "reviewed-site-packet.json"
    rows_path = attempt / "rows.json"
    site = json.loads(site_path.read_text())["site"]
    rows = json.loads(rows_path.read_text())
    require(len(rows) == 900 and all(row.get("original_frame") == 300 + i and
            abs(row.get("time_s", -1) - i / 20) < 1e-6 for i, row in enumerate(rows)),
            "900 source-time joined physical rows missing")
    require(kind in ("complete_motion", "incomplete_motion", "missing_evidence"),
            "unknown physical fixture kind")
    if kind == "incomplete_motion":
        for row in rows:
            row["ego_leading_station_m"] = -2
            row["ego_across_or_within"] = False
    elif kind == "missing_evidence":
        rows[120].pop("ego_leading_station_m")
    reference = site["physical_reference_station_m"]
    if any(type(row.get("ego_leading_station_m")) not in (int, float) or
           type(row.get("ego_across_or_within")) is not bool for row in rows):
        status, crossing = "unverified", []
    else:
        crossing = [row["original_frame"] for row in rows
                    if row["ego_leading_station_m"] >= reference and
                    row["ego_across_or_within"]]
        status = "met" if rows[0]["ego_leading_station_m"] < reference and crossing else "not_met"
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    require(status == expected, "synthetic motion fixture outcome differs")
    return {"case_id": case.case_id, "kind": kind,
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "maneuver_completed": status == "met",
            "physical_checks": {"maneuver": {"status": status,
                "method": "900 original-frame ego-leading-station and across/within join against reviewed physical reference",
                "sources": [{"path": str(rows_path), "sha256": digest(rows_path)},
                            {"path": str(site_path), "sha256": digest(site_path)}]}},
            "realized_observables": {"first_crossing_frame": crossing[0],
                                     "crossing_frame_count": len(crossing),
                                     "physical_reference_station_m": reference}
                                    if status == "met" else {},
            "physical_completion_claimed": False,
            "legal_judgment": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    case = next((item for item in CASES if args.case.endswith("__" + item.case_id)), None)
    require(case is not None, "unknown exact physical case")
    require(not args.output.exists(), "physical fixture result already exists")
    result = evaluate(args.attempt, case, args.kind)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "kind": args.kind,
                      "status": result["physical_checks"]["maneuver"]["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
