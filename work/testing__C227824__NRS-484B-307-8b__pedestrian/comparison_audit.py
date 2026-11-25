"""Independent diagnostic comparison of C227824 saved measurements.

The paired audit verifies source joins and controlled conditions. It does not
interpret NRS 484B.283 or certify a Native recording.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from saved_entry import build_report


def audit_pair(left, right, *, comparison_id, deliberate_difference):
    if deliberate_difference not in {"entry_request", "other_device_indication"}:
        raise ValueError("undeclared comparison variable")
    if not isinstance(comparison_id, str) or not comparison_id:
        raise ValueError("comparison identity missing")
    if not isinstance(left, dict) or not isinstance(right, dict):
        raise ValueError("paired saved reports missing")
    for report in (left, right):
        for key in ("case_id", "map_sha256", "highway_boundary_sha256",
                    "facing_signal_id", "actor_blueprint", "route_id",
                    "camera_plan_sha256", "entry_request", "measurement"):
            if key not in report or report[key] is None or report[key] == "":
                raise ValueError("paired saved report missing " + key)
        measured = report["measurement"]
        if not isinstance(measured, dict) or measured.get("measurement_only") is not True or measured.get("legal_permission_determined") is not False:
            raise ValueError("unbound or overclaimed entry measurement")
        event = measured.get("first_entry")
        if measured.get("entry_observed") is not (event is not None):
            raise ValueError("entry event disagrees with measurement status")
        if event is not None:
            signal = event.get("facing_traffic_signal")
            if not isinstance(signal, dict) or signal.get("official") is not True or signal.get("indication") != "steady_red_alone":
                raise ValueError("entry frame lacks official facing steady red alone")
            if not isinstance(event.get("other_devices"), list):
                raise ValueError("entry frame lacks other-device inventory")
    if left["case_id"] == right["case_id"]:
        raise ValueError("comparison requires different exact cases")
    fixed = ("map_sha256", "highway_boundary_sha256", "facing_signal_id",
             "actor_blueprint", "route_id", "camera_plan_sha256")
    for key in fixed:
        if left[key] != right[key]:
            raise ValueError("fixed comparison condition differs: " + key)
    if deliberate_difference == "entry_request":
        if {left["entry_request"], right["entry_request"]} != {"entry", "wait"}:
            raise ValueError("entry/wait movement request was not isolated")
        for report in (left, right):
            if report.get("planned_device_indication") != "none":
                raise ValueError("entry/wait comparison changed another device")
    else:
        if left["entry_request"] != "entry" or right["entry_request"] != "entry":
            raise ValueError("device comparison changed movement request")
        if left.get("planned_device_indication") == right.get("planned_device_indication"):
            raise ValueError("separate device indication did not vary")
        if "none" not in {left.get("planned_device_indication"), right.get("planned_device_indication")}:
            raise ValueError("device comparison needs red-alone reference")
        for report in (left, right):
            event = report["measurement"]["first_entry"]
            if event is None:
                raise ValueError("device comparison lacks observed first entry")
            indications = [device.get("indication") for device in event["other_devices"] if device.get("official") is True]
            expected = report["planned_device_indication"]
            if expected == "none" and indications:
                raise ValueError("red-alone reference has another official device")
            if expected != "none" and indications != [expected]:
                raise ValueError("planned device disagrees with original entry frame")
    return {"comparison_id": comparison_id, "case_ids": [left["case_id"], right["case_id"]],
            "fixed_source_conditions_checked": list(fixed),
            "deliberate_difference_checked": deliberate_difference,
            "diagnostic_audit_passed": True,
            "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}


def audit_attempts(left_attempt, right_attempt, comparison_id, plan_path):
    """Read source-bound saved attempts and enforce the frozen comparison pair."""
    plan = json.loads(Path(plan_path).read_text())
    matches = [item for item in plan["comparisons"]
               if item["comparison_id"] == comparison_id]
    if len(matches) != 1:
        raise ValueError("exact comparison identity missing")
    left = build_report(left_attempt)
    right = build_report(right_attempt)
    pair = matches[0]
    if [left["case_id"], right["case_id"]] != pair["case_ids"]:
        raise ValueError("saved attempts differ from exact comparison pair")
    difference = ("entry_request" if comparison_id == "red_entry_vs_wait"
                  else "other_device_indication")
    result = audit_pair(left, right, comparison_id=comparison_id,
                        deliberate_difference=difference)
    result["source_sha256"] = {left["case_id"]: left["source_sha256"],
                               right["case_id"]: right["source_sha256"]}
    result["diagnostic_fixture"] = (left["diagnostic_fixture"] or
                                     right["diagnostic_fixture"])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left-attempt", required=True)
    parser.add_argument("--right-attempt", required=True)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--plan", default=str(Path(__file__).resolve().parent /
                                               "case-plan.json"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = audit_attempts(args.left_attempt, args.right_attempt,
                            args.comparison_id, args.plan)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"comparison_id": result["comparison_id"],
                      "diagnostic_fixture": result["diagnostic_fixture"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
