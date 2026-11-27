"""Independent exact-case comparison of original source-bound pass attempts.

This preserves the planned single-variable contrast. It records measured
differences without converting due care or lane safety into a legal verdict.
"""

import argparse
import hashlib
import json
from pathlib import Path

from package_spec import AID


HERE = Path(__file__).resolve().parent
FIELDS = ("control_kind", "same_direction_lane_count_requested",
          "left_lane_traffic_requested", "ego_maneuver_request")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def intended_difference(comparison_id):
    if comparison_id == "control_kind":
        return "control_kind"
    if comparison_id.endswith("_occupancy"):
        return "left_lane_traffic_requested"
    if comparison_id.endswith("_open_move") or comparison_id == "one_lane_due_care":
        return "ego_maneuver_request"
    raise ValueError("unknown exact comparison")


def assess(comparison_id, records, *, diagnostic=False):
    plan = json.loads((HERE / "case-plan.json").read_text())
    need(plan["assignment_id"] == AID, "comparison assignment changed")
    comparisons = [row for row in plan["comparisons"] if row["comparison_id"] == comparison_id]
    need(len(comparisons) == 1, "exact comparison missing")
    comparison = comparisons[0]
    case_ids = comparison["case_ids"]
    need(set(records) == set(case_ids) and len(records) == len(case_ids),
         "comparison case coverage differs")
    cases = {row["case_id"]: row for row in plan["cases"]}
    need(all(case_id in cases for case_id in case_ids), "comparison case missing from plan")
    changed = [field for field in FIELDS
               if len({cases[case_id][field] for case_id in case_ids}) > 1]
    need(changed == [intended_difference(comparison_id)],
         "comparison changed unplanned world or controller variable")
    source_receipts = set()
    map_hashes = set()
    measured = {}
    for case_id in case_ids:
        row = records[case_id]
        need(row.get("case_id") == case_id and row.get("frame_count") == 900 and
             row.get("full_decode") is True and row.get("actual_pixels") is True,
             "comparison original source/decode/pixel evidence incomplete")
        need(row.get("physical_status") in {"met", "not_met", "unverified"} and
             row.get("legal_verdict") is None,
             "comparison physical result or legal scope invalid")
        receipt = row.get("receipt_sha256")
        map_hash = row.get("native_map_sha256")
        need(isinstance(receipt, str) and len(receipt) == 64 and
             isinstance(map_hash, str) and len(map_hash) == 64,
             "comparison source hashes missing")
        source_receipts.add(receipt)
        map_hashes.add(map_hash)
        values = row.get("measurements")
        need(isinstance(values, dict) and
             {"activation", "due_care_sources", "lane_topology", "lane_movement"} <= set(values),
             "comparison selected source measurements missing")
        measured[case_id] = values
        if comparison_id.endswith("_stay_occupancy"):
            occupants = row.get("initial_left_lane_occupied_actor_ids")
            need(isinstance(occupants, list) and
                 all(isinstance(actor, str) and actor for actor in occupants),
                 "original initial left-lane traffic inventory missing")
            requested = cases[case_id]["left_lane_traffic_requested"]
            need((requested == "occupied") == bool(occupants),
                 "original left-lane traffic does not match controlled occupancy")
    need(len(source_receipts) == len(case_ids), "comparison reused original case receipt")
    need(len(map_hashes) == 1, "comparison source map differs across fixed road context")
    return {"format": "pass-exact-comparison-audit", "comparison_id": comparison_id,
            "case_ids": case_ids, "difference": changed[0],
            "native_map_sha256": next(iter(map_hashes)),
            "measured": measured, "physical_statuses": {case_id: records[case_id]["physical_status"]
                                                      for case_id in case_ids},
            "diagnostic_fixture": diagnostic, "source_verified": not diagnostic,
            "legal_verdict": None, "canonical_acceptance": False}


def from_attempts(comparison_id, manifest_path):
    from pass_capture_audit import audit as capture_audit
    manifest = json.loads(Path(manifest_path).read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    comparison = next(row for row in plan["comparisons"] if row["comparison_id"] == comparison_id)
    records = {}
    for case_id in comparison["case_ids"]:
        item = manifest[case_id]
        attempt = Path(item["attempt"]).resolve()
        source = capture_audit(attempt, case_id)
        delivery = json.loads(Path(item["delivery_audit"]).read_text())
        physical = json.loads(Path(item["physical_result"]).read_text())
        analysis_path = Path(item.get("analysis_report", attempt / "analysis-report.json"))
        analysis = json.loads(analysis_path.read_text())
        context = json.loads((attempt / "original-context.json").read_text())
        original_trace = (attempt / "original-trace.jsonl").read_text().splitlines()
        need(len(original_trace) == source["frame_count"],
             "original actor trace frame count differs")
        first = json.loads(original_trace[0])
        need(delivery.get("source_verified") is True and
             delivery.get("capture_receipt_sha256") == source["receipt_sha256"],
             "independent original delivery review missing")
        records[case_id] = {"case_id": case_id, "frame_count": source["frame_count"],
                            "full_decode": source["full_decode"], "actual_pixels": True,
                            "physical_status": physical["physical_checks"]["maneuver"]["status"],
                            "legal_verdict": None, "receipt_sha256": source["receipt_sha256"],
                            "native_map_sha256": context["map_sha256"],
                            "initial_left_lane_occupied_actor_ids": first.get("left_lane_occupied_actor_ids"),
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
    result = assess(args.comparison, json.loads(Path(args.records).read_text()), diagnostic=True) if args.records else \
        from_attempts(args.comparison, args.attempts)
    print(json.dumps(result, indent=2))
