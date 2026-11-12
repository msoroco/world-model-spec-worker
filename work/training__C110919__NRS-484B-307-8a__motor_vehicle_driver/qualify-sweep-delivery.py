"""Promote the two CPU-probed physical grids to assignment-qualified case IDs.

This changes delivery identity only. The frozen sweep axes and measured-versus-
authored variable distinction stay intact; no original Native motion is claimed.
"""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    plan = read(HERE / "case-plan.json")
    if len(plan["cases"]) == 20:
        current = read(HERE / "proposals/cases.json")
        selected = [c["case_id"] for c in current["cases"]
                    if c["target_type"] != "baseline"]
        if len(selected) != 20 or selected != [c["case_id"] for c in plan["cases"]]:
            raise ValueError("Existing qualified stage and plan differ")
        print(json.dumps({"qualified_sweep_cases": 10,
                          "planned_cases": 20, "selection_count": 20,
                          "already_qualified": True}))
        return
    source = read(HERE / "proposals/extreme-right-sweep-candidate.json")
    stage = copy.deepcopy(source)
    sweep_cases = [case for case in stage["cases"] if case.get("sweep_id")]
    if len(sweep_cases) != 10 or len(plan["cases"]) not in (10, 20):
        raise ValueError("Unexpected source or plan case count")
    identity = {case["case_id"]: AID + "__" + case["case_id"] for case in sweep_cases}
    for case in sweep_cases:
        case["case_id"] = identity[case["case_id"]]
    for spec in stage["sweep_specs"]:
        spec["selection_order"] = [identity.get(cid, cid) for cid in spec["selection_order"]]
    for disposition in plan["requirement_dispositions"]:
        disposition["case_ids"] = [identity.get(cid, cid) for cid in disposition["case_ids"]]
        if disposition["requirement"] == "text-1":
            disposition["status"] = "selected_required"
            disposition["evidence_or_gap"] += (
                " Paragraph (d) listed actor classes do not describe the assigned"
                " motor-vehicle driver; selected CPU cases plan stop-boundary and"
                " green-release observations. Actual motion and signal state"
                " remain for original Native review."
            ) if "selected CPU cases plan stop-boundary" not in disposition["evidence_or_gap"] else ""
    if len(plan["cases"]) == 10:
        for case in sweep_cases:
            name = case["case_id"]
            axis = next(iter(case["sweep_point"]))
            plan["cases"].append({
                "case_id": name,
                "target_law_id": case["target_law_id"],
                "planning_status": "unverified_definition",
                "target_type": "judgment_sweep",
                "comparison_variable": axis,
                "comparison_unit": "frame" if axis == "traffic_launch_frame" else "m",
                "requested_setting": case["sweep_point"][axis],
                "recorded_value": None,
                "case_description": case["rationale"],
                "fixed_context": "Hold the other authored controls and map geometry fixed; measure original Native actor motion and full-body position after capture.",
                "source_topic_ids": ["text-0", "text-1", "text-2"],
                "gap_ids": ["right_turn_permission_and_yield", "selected_delivery_comparison"],
            })
        for sweep_id, axis in (("C110919-right-of-way", "traffic_launch_frame"),
                               ("C110919-extreme-right", "lateral_right_offset_m")):
            plan["comparisons"].append({
                "comparison_id": AID + "__comparison_" + sweep_id.replace("-", "_"),
                "case_ids": [c["case_id"] for c in sweep_cases if c["sweep_id"] == sweep_id],
                "deliberate_differences": [axis],
                "fixed_conditions": ["cell", "actor", "ego_red_signal", "receiving_road",
                                     "pedestrian_path", "noncompared_controller_settings",
                                     "weather", "camera_and_capture_profile"],
                "status": "planned_unverified",
            })
    else:
        if [c["case_id"] for c in plan["cases"][10:]] != [c["case_id"] for c in sweep_cases]:
            raise ValueError("Existing qualified case plan differs")
    stage["promotion_note"] = (
        "Twenty assignment-qualified proposed delivery cases; 80 synthetic CPU"
        " candidate bundles are historical probes. Original Native observations"
        " and independent physical review remain pending."
    )
    stage["candidate_only"] = False
    stage["original_native_accepted"] = False
    save(HERE / "proposals/cases.json", stage)
    save(HERE / "case-plan.json", plan)
    print(json.dumps({"qualified_sweep_cases": len(sweep_cases),
                      "planned_cases": len(plan["cases"]),
                      "selection_count": len([c for c in stage["cases"] if c["target_type"] != "baseline"])}))


if __name__ == "__main__":
    main()
