"""Independent controlled comparison of exact source-bound delivery audits."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOUNDARY = 4.572


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison_id, report_dir, *, synthetic_fixture=False):
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    comparison = next((item for item in plan["comparisons"]
                       if item["comparison_id"] == comparison_id), None)
    if comparison is None:
        raise ValueError("unknown exact projection comparison")
    report_dir = Path(report_dir)
    reports = []
    for case_id in comparison["case_ids"]:
        path = report_dir / (case_id.rsplit("__", 1)[-1] + ".json")
        value = json.loads(path.read_text(encoding="utf-8"))
        if (value.get("format") != "worker-delivery-audit" or value.get("passed") is not True or
                value.get("case_id") != case_id or value.get("legal_verdict_claimed") is not False):
            raise ValueError("exact source-bound delivery audit missing: " + case_id)
        if not synthetic_fixture and value.get("scope") != "original Native delivery review":
            raise ValueError("synthetic comparison cannot establish original delivery")
        reports.append((path, value))
    fixed = ("cell_id", "actor", "road_sha256", "curb_geometry_sha256",
             "camera_contract_sha256", "duration_s", "candidate_id")
    first = reports[0][1]
    for _, report in reports[1:]:
        if any(report.get(key) != first.get(key) for key in fixed):
            raise ValueError("controlled comparison changed fixed curb, camera, candidate or duration")
    values = [report["maximum_perpendicular_projection_m"] for _, report in reports]
    if comparison_id == "fifteen_foot_boundary":
        if not values[0] < values[1] < values[2]:
            raise ValueError("observed boundary probe ordering differs")
        if [report["controlling_part"] for _, report in reports] != ["vehicle"] * 3:
            raise ValueError("boundary probe changed controlling physical part")
    elif comparison_id in ("part_of_load", "attached_trailer"):
        expected = "load" if comparison_id == "part_of_load" else "trailer"
        if [report["controlling_part"] for _, report in reports] != ["vehicle", expected]:
            raise ValueError("extended physical part missing from comparison")
        if abs(reports[0][1]["vehicle_base_projection_m"] -
               reports[1][1]["vehicle_base_projection_m"]) > .08:
            raise ValueError("load/trailer comparison changed the fixed vehicle body projection")
        if not values[0] < values[1]:
            raise ValueError("extended part did not increase measured projection")
    return {"format": "worker-comparison-audit", "comparison_id": comparison_id,
            "passed": True, "case_ids": comparison["case_ids"],
            "reports_sha256": {path.name: sha(path) for path, _ in reports},
            "fixed_conditions_checked": list(fixed),
            "deliberate_differences": comparison["deliberate_differences"],
            "measured_projection_m": values, "statutory_boundary_m": BOUNDARY,
            "engineering_tolerance_is_legal_boundary": False,
            "scope": "synthetic CPU comparison proof only" if synthetic_fixture else "original Native delivery review",
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--report-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.report_dir), indent=2))
