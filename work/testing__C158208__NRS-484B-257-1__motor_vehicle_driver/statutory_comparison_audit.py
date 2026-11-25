"""Compare exact C158208 saved histories without making a legal judgment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from selected_delivery_audit import audit as audit_delivery
from source_tick_capture import verify_seal


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
PHASE_COMPARISONS = {"occupied_or_approaching_traffic", "across_or_within_history"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(stages: dict[str, Path], *, diagnostic_fixture: bool,
          reviewed_expectations: dict | None = None) -> dict:
    plan = json.loads((HERE / "case-plan.json").read_text())
    expected_cases = {case["case_id"] for case in plan["cases"]}
    if set(stages) != expected_cases:
        raise ValueError("comparison requires every exact accepted case")
    if not diagnostic_fixture and (not isinstance(reviewed_expectations, dict) or
                                   set(reviewed_expectations) != expected_cases):
        raise ValueError("production comparison requires independent original-source expectations")
    observed = {}
    for case_id in sorted(expected_cases):
        stage = Path(stages[case_id])
        delivery = audit_delivery(stage, case_id=case_id,
                                  diagnostic_fixture=diagnostic_fixture)
        packet = verify_seal(stage)
        identity = json.loads((stage / "capture-identity.json").read_text())
        if not diagnostic_fixture:
            expected = reviewed_expectations[case_id]
            for field in ("construction_sha256", "site_packet_sha256", "map_opendrive_sha256"):
                if identity.get(field) != expected.get(field):
                    raise ValueError("original comparison source differs: " + case_id + " " + field)
        report = json.loads((stage / "analysis-report.json").read_text())
        history = report["measurements"].get("statutory_branch_history") or \
                  report["measurements"].get("nearest_view_history")
        if not isinstance(history, dict):
            raise ValueError("selected case history missing")
        value = history["value"]
        rows = packet["samples"]
        observed[case_id] = {
            "delivery_report_sha256": delivery["report_sha256"],
            "capture_identity_sha256": sha(stage / "capture-identity.json"),
            "geometry": packet["geometry"],
            "governing_context": {name: packet["reviewed_context"].get(name)
                                  for name in ("yield_sign_governs_approach",
                                               "through_highway_confirmed",
                                               "no_officer_control", "no_signal_control")},
            "reference_branch": value.get("reference_branch", "nearest_view"),
            "minimum_approach_speed_mps": value["minimum_approach_speed_mps"],
            "through_history": [[row["through_center_station_m"],
                                 row["through_vehicle_within_intersection"]] for row in rows],
            "ego_crossing": [row["intersection_entry"] for row in rows],
        }
    comparisons = []
    for entry in plan["comparisons"]:
        members = [observed[case_id] for case_id in entry["case_ids"]]
        branch = entry["comparison_id"]
        if any(row["geometry"] != members[0]["geometry"] or
               row["governing_context"] != members[0]["governing_context"]
               for row in members[1:]):
            raise ValueError("fixed original geometry or governing control differs: " + branch)
        if branch not in PHASE_COMPARISONS:
            if any(row["through_history"] != members[0]["through_history"]
                   for row in members[1:]):
                raise ValueError("fixed through-traffic history differs: " + branch)
        if branch in ("yield_nearest_view", "nearest_view_no_line_or_crosswalk",
                      "yield_slowed_or_stopped", "marked_stop_line_priority",
                      "near_side_marked_crosswalk_priority",
                      "near_side_sidewalk_crosswalk_priority") and any(
                          row["reference_branch"] != members[0]["reference_branch"]
                          for row in members[1:]):
            raise ValueError("fixed stopping reference differs: " + branch)
        speeds = {row["minimum_approach_speed_mps"] for row in members}
        traffic = {json.dumps(row["through_history"]) for row in members}
        realized = len(traffic if branch in PHASE_COMPARISONS else speeds) > 1
        if not diagnostic_fixture and not realized:
            raise ValueError("original deliberate comparison difference not realized: " + branch)
        comparisons.append({"comparison_id": branch, "case_ids": entry["case_ids"],
                            "status": "synthetic_software_only" if diagnostic_fixture else
                                      "source_bound_measurement_for_review",
                            "fixed_geometry_and_governing_control": True,
                            "through_history_fixed": branch not in PHASE_COMPARISONS,
                            "deliberate_difference_observed": realized,
                            "minimum_approach_speed_mps": {
                                case_id: observed[case_id]["minimum_approach_speed_mps"]
                                for case_id in entry["case_ids"]},
                            "source_report_sha256": {
                                case_id: observed[case_id]["delivery_report_sha256"]
                                for case_id in entry["case_ids"]},
                            "legal_status": "unresolved"})
    return {"format": "c158208-statutory-comparison-audit-v1",
            "assignment_id": ASSIGNMENT, "diagnostic_fixture": diagnostic_fixture,
            "comparisons": comparisons, "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stages", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--reviewed-expectations", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("comparison audit output already exists")
    mapping = {key: Path(value) for key, value in json.loads(args.stages.read_text()).items()}
    expectations = (json.loads(args.reviewed_expectations.read_text())
                    if args.reviewed_expectations else None)
    result = audit(mapping, diagnostic_fixture=args.diagnostic_fixture,
                   reviewed_expectations=expectations)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(len(result["comparisons"]))
