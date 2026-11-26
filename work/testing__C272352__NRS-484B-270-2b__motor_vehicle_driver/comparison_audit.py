"""Independent exact-case comparison of passing geometry and fixed site context."""

import argparse
import hashlib
import json
from pathlib import Path

from build_selected_draft import AID, case_parameters


HERE = Path(__file__).resolve().parent
FIELDS = ("control_kind", "target_clearance_m", "return_request", "route_request")
DIFFERENCE = {"three_foot_clearance": "target_clearance_m",
              "return_right_order": "return_request",
              "participant_alternatives": "control_kind",
              "special_route_authorizations": "route_request"}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def assess(comparison_id, records, *, diagnostic=False):
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    need(plan["assignment_id"] == AID, "comparison assignment changed")
    comparison = next((row for row in plan["comparisons"]
                       if row["comparison_id"] == comparison_id), None)
    need(comparison is not None and comparison_id in DIFFERENCE,
         "exact planned comparison required")
    ids = comparison["case_ids"]
    need(set(records) == set(ids) and len(records) == len(ids),
         "exact comparison case coverage required")
    parameters = {ident: case_parameters(ident.removeprefix(AID + "__"))
                  for ident in ids}
    changed = [field for field in FIELDS if len({parameters[ident][field]
                                                for ident in ids}) > 1]
    need(changed == [DIFFERENCE[comparison_id]],
         "unplanned case parameter differs in controlled comparison")
    site_hashes = set()
    receipts = set()
    measurements = {}
    for ident in ids:
        row = records[ident]
        need(row.get("case_id") == ident and row.get("frame_count") == 900 and
             row.get("full_decode") is True and row.get("actual_pixels") is True,
             "original full-frame decode or pixel evidence incomplete")
        need(row.get("physical_status") in {"met", "not_met", "unverified"} and
             row.get("legal_verdict") is None,
             "physical/legal review boundary changed")
        site = row.get("native_map_sha256")
        receipt = row.get("receipt_sha256")
        need(all(isinstance(value, str) and len(value) == 64
                 for value in (site, receipt)), "original source hash missing")
        site_hashes.add(site)
        receipts.add(receipt)
        values = row.get("measurements")
        need(isinstance(values, dict) and "left_clearance" in values,
             "source-bound pass measurement missing")
        measurements[ident] = values["left_clearance"]
    need(len(site_hashes) == 1, "fixed Native map/source context changed")
    need(len(receipts) == len(ids), "original receipt reused across cases")
    return {"format": "passing-exact-comparison-audit", "comparison_id": comparison_id,
            "case_ids": ids, "difference": changed[0],
            "native_map_sha256": next(iter(site_hashes)),
            "measurements": measurements, "diagnostic_fixture": diagnostic,
            "source_verified": not diagnostic, "legal_verdict": None,
            "canonical_acceptance": False}


def from_attempts(comparison_id, manifest_path):
    from passing_capture_audit import audit as capture_audit
    from delivery_audit import assess as delivery_assess
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    comparison = next(row for row in plan["comparisons"]
                      if row["comparison_id"] == comparison_id)
    records = {}
    for ident in comparison["case_ids"]:
        item = manifest[ident]
        attempt = Path(item["attempt"]).resolve()
        capture = capture_audit(attempt, ident)
        review = json.loads(Path(item["pixel_review"]).read_text(encoding="utf-8"))
        physical = json.loads(Path(item["physical_result"]).read_text(encoding="utf-8"))
        delivery = delivery_assess(ident, capture, review, physical, attempt=attempt)
        need(delivery["source_verified"] is True,
             "independent original delivery review missing")
        analysis = json.loads(Path(item.get("analysis_report",
                                            attempt / "analysis-report.json")).read_text(encoding="utf-8"))
        context = json.loads((attempt / "original-context.json").read_text(encoding="utf-8"))
        records[ident] = {"case_id": ident, "frame_count": capture["frame_count"],
                          "full_decode": capture["full_decode"], "actual_pixels": True,
                          "physical_status": physical["physical_checks"]["maneuver"]["status"],
                          "legal_verdict": None, "native_map_sha256": context["map_sha256"],
                          "receipt_sha256": capture["receipt_sha256"],
                          "measurements": analysis["measurements"]}
    return assess(comparison_id, records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--records")
    parser.add_argument("--attempts")
    args = parser.parse_args()
    if bool(args.records) == bool(args.attempts):
        raise ValueError("select diagnostic records or original attempts")
    result = (assess(args.comparison,
                     json.loads(Path(args.records).read_text(encoding="utf-8")),
                     diagnostic=True) if args.records else
              from_attempts(args.comparison, args.attempts))
    print(json.dumps(result, indent=2))
