"""Independent fixed-context audit of exact crosswalk pair differences."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import crosswalk_site as crossing
from crosswalk_measure import measure, require_file


def audit(attempts, comparison_id, plan):
    planned = json.loads(Path(plan).read_text())
    row = next((item for item in planned["comparisons"]
                if item["comparison_id"] == comparison_id), None)
    if row is None or len(attempts) != len(row["case_ids"]):
        raise ValueError("unknown exact crosswalk comparison")
    sites, measured, diagnostics = [], [], []
    for attempt, case_id in zip(attempts, row["case_ids"]):
        attempt = Path(attempt)
        site = json.loads(require_file(attempt, "original-site.json").read_text())
        fixture = (attempt / "fixture-provenance.json").is_file()
        packet = json.loads(require_file(attempt, "original-crosswalk-history.json").read_text())
        if (packet.get("case_id") != case_id or site.get("case_id", case_id) != case_id or
                not case_id.startswith(crossing.ASSIGNMENT_ID + "__")):
            raise ValueError("comparison case identity mismatch")
        sites.append(site)
        diagnostics.append(fixture)
        measured.append(measure(attempt, case_id, diagnostic=fixture))
    fixed = ("assignment_id", "cell_id", "actor", "crossing_polygon_xy_m",
             "road_id", "lane_id")
    if any(any(site.get(key) != sites[0].get(key) for key in fixed)
           for site in sites[1:]):
        raise ValueError("comparison fixed crossing context differs")
    if not all(diagnostics):
        source_keys = ("jurisdiction", "vehicle_identity", "responsible_person",
                       "vehicle_route", "road_geometry")
        if any(any(site.get(key + "_source_sha256") != sites[0].get(key + "_source_sha256")
                   for key in source_keys) for site in sites[1:]):
            raise ValueError("comparison independent fixed sources differ")
    first, second = sites
    differing = {key for key in ("requested_body_clearance_m", "requested_activity",
                                 "requested_exception", "crosswalk_marked")
                 if first.get(key) != second.get(key)}
    index = int(comparison_id.rsplit("_", 1)[-1])
    expected = ({1: {"requested_body_clearance_m"},
                 2: {"requested_body_clearance_m"},
                 3: {"requested_activity"}, 4: {"requested_activity"},
                 5: {"requested_activity", "requested_exception"},
                 6: {"requested_activity", "requested_exception"},
                 7: {"requested_activity", "requested_exception"},
                 8: {"crosswalk_marked"}})[index]
    if differing != expected:
        raise ValueError("comparison deliberate difference changed")
    if any(item["legal_measurement_convention"] != "unresolved" or
           item["exception_judgment"] != "unresolved" for item in measured):
        raise ValueError("comparison inserted legal judgment")
    return {"format": "c394507-independent-crosswalk-comparison-audit-v1",
            "assignment_id": crossing.ASSIGNMENT_ID,
            "comparison_id": comparison_id,
            "case_ids": row["case_ids"],
            "measured_body_clearances_m": [item["body_clearance_min_m"] for item in measured],
            "fixed_context_checked": True,
            "deliberate_difference_checked": True,
            "diagnostic_fixture": all(diagnostics),
            "physical_acceptance_claimed": False,
            "legal_judgment": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, action="append", required=True)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite independent comparison audit")
    value = audit(args.attempt, args.comparison_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
