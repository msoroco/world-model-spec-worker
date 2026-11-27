"""Expand the exact grade-crossing branch into source-gated CPU case targets."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def build():
    path = HERE / "case-plan.json"
    plan = json.loads(path.read_text())
    branch = "Crossing traversal under the stated sight conditions without either exception."
    specs = (
        ("obscured_14mph", 14, "obscured", "none"),
        ("obscured_15mph", 15, "obscured", "none"),
        ("obscured_16mph", 16, "obscured", "none"),
        ("clear_view_16mph", 16, "clear", "none"),
        ("flagman_16mph", 16, "obscured", "flagman_on_duty"),
        ("signal_nonwarning_16mph", 16, "obscured", "visible_nonwarning_signal"),
        ("signal_warning_16mph", 16, "obscured", "visible_warning_signal"),
    )
    branches = {
        "none": branch,
        "flagman_on_duty": "On-duty flagman exception during grade-crossing traversal.",
        "visible_nonwarning_signal": "Clearly visible installed nonwarning crossing-signal exception during traversal.",
        "visible_warning_signal": "Warning crossing signal during traversal; nonwarning exception is not established.",
    }
    plan["selected_branch"] = branch
    plan["source_observation_mapping"] = {}
    review = plan.setdefault("evidence_review", {})
    review["gaps"] = [{
        "gap_id": "no-accepted-original-grade-crossing-recording",
        "reason": "The frozen evidence inventory contains no accepted original recording for this assigned grade-crossing branch.",
        "source": "inputs/" + AID + "/evidence.json",
    }]
    plan["cases"] = [
        {"case_id": AID + "__" + name, "target_law_id": "LVMC-11-16-030",
         "kind": "delivery",
         "branch": ("Clear-view comparison outside the sight-conditioned branch."
                    if sight == "clear" else branches[exception]),
         "engineering_target_traversal_mph": mph,
         "engineering_sight_setup": sight, "exception_setup": exception,
         "candidate_risk": {"status": "physical", "reason":
             "Reviewed original grade-crossing geometry, sight rays and speed may miss the requested condition; actual Native readback determines feasibility."},
         "construction_probe": "rail_sight_measurement.py",
         "gap_ids": ["no-accepted-original-grade-crossing-recording"]}
        for name, mph, sight, exception in specs]
    by_name = {name: AID + "__" + name for name, *_ in specs}
    plan["comparisons"] = [
        {"comparison_id": "obscured_speed_boundary",
         "case_ids": [by_name[name] for name in
                      ("obscured_14mph", "obscured_15mph", "obscured_16mph")],
         "fixed_conditions": ["same reviewed rail crossing, 100-foot approach sight obstruction, no exception, vehicle, camera and measurement method"],
         "deliberate_differences": ["original measured traversal speed around the 15 mph prima facie boundary"]},
        {"comparison_id": "obscured_versus_clear_view",
         "case_ids": [by_name[name] for name in
                      ("obscured_16mph", "clear_view_16mph")],
         "fixed_conditions": ["same crossing, vehicle, traversal speed target, no exception and camera contract"],
         "deliberate_differences": ["original crossing and bidirectional 400-foot railway sight-ray result during last 100 feet of approach"]},
        {"comparison_id": "flagman_and_signal_exceptions",
         "case_ids": [by_name[name] for name in
                      ("obscured_16mph", "flagman_16mph", "signal_nonwarning_16mph", "signal_warning_16mph")],
         "fixed_conditions": ["same obscured crossing, vehicle, traversal speed target and camera contract"],
         "deliberate_differences": ["on-duty flagman, clearly visible nonwarning signal, or warning signal that does not qualify for the exception"]},
    ]
    plan["observations"] = [
        {"name": "reviewed_municipal_rail_site", "mandatory": True,
         "description": "Source-hashed original map and review establish municipal at-grade railway crossing and 100/400-foot extents."},
        {"name": "original_approach_sight_rays", "mandatory": True,
         "description": "Original-frame source-hashed rays to crossing and 400 feet in both rail directions during last 100 feet of approach."},
        {"name": "original_crossing_speed", "mandatory": True,
         "description": "Original body crossing occupancy and measured traversal speed against 15 mph; approach speed is not the governed measure."},
        {"name": "flagman_and_signal_state", "mandatory": True,
         "description": "Original on-duty flagman and visible signal installation plus contemporaneous immediate-train-approach indication."},
        {"name": "original_four_camera_pixels", "mandatory": True,
         "description": "Four synchronized original views and frame joins show approach, track, crossing and vehicle."},
    ]
    plan["requirement_dispositions"] = [
        {"requirement": "Sight-conditioned 15 mph prima facie speed during railway grade-crossing traversal",
         "source": "LVMC 11.16.030", "status": "selected_required",
         "evidence_or_gap": "Original site, approach ray, body traversal and speed sources required; engineering targets do not prove outcomes.",
         "case_ids": [by_name[name] for name in ("obscured_14mph", "obscured_15mph", "obscured_16mph", "clear_view_16mph")]},
        {"requirement": "On-duty human flagman exception",
         "source": "LVMC 11.16.030", "status": "selected_required",
         "evidence_or_gap": "Original duty state and crossing time source required.",
         "case_ids": [by_name["obscured_16mph"], by_name["flagman_16mph"]]},
        {"requirement": "Clearly visible installed electrical or mechanical nonwarning signal exception",
         "source": "LVMC 11.16.030", "status": "selected_required",
         "evidence_or_gap": "Original installation, visibility and contemporaneous indication sources required.",
         "case_ids": [by_name[name] for name in
                      ("obscured_16mph", "signal_nonwarning_16mph", "signal_warning_16mph")]},
    ]
    plan["planning_status"] = "source_bound_case_construction_in_progress"
    plan["runtime_uncertainties"] = [
        "Reviewed municipal rail crossing, original OpenDRIVE, source-hashed approach ray, signal and flagman packets must be supplied at local run.",
        "Virtual sight rays do not settle the legal meaning of clear and unobstructed driver view; legal judgment remains unresolved.",
        "Selected production bundles, semantic proposals and full CPU delivery proofs remain worker construction work."]
    path.write_text(json.dumps(plan, sort_keys=True, indent=2) + "\n")
    return len(plan["cases"]), len(plan["comparisons"])


if __name__ == "__main__":
    print(*build())
