"""Draft canonical case proposals for the fixed safety-zone cell."""

import json
from pathlib import Path

from case_specs import CASES
from build_construction import DESCRIPTION

FOLDER = Path(__file__).resolve().parents[1]


def build():
    common = {
        "position_request": {"kind": "controller", "value": None, "unit": "category"},
        "requested_curb_end_gap_ft": {"kind": "controller", "value": None, "unit": "ft"},
        "activity_request": {"kind": "controller", "value": None, "unit": "category"},
        "exception_request": {"kind": "controller", "value": None, "unit": "category"},
        "observed_zone_and_exception_state": {"kind": "subject_behavior", "value": None,
                                              "unit": "structured"},
    }
    cases = [{"case_id": FOLDER.name + "__baseline", "target_law_id": None,
              "target_type": "baseline", "cell_id": "C150660",
              "actor": "motor_vehicle_driver",
              "rationale": "Unselected fixed road and driver context.",
              "recording_description": DESCRIPTION,
              "unresolved_judgment_calls": [], "variable_assignments": common}]
    for suffix, (position, activity, exception, gap_ft) in CASES.items():
        case = FOLDER.name + "__" + suffix
        if suffix.startswith(("end_", "start_", "selected_")):
            differences = ["requested_curb_end_gap_ft", "position_request"]
        else:
            differences = ["exception_request" if exception != "none" else
                           "activity_request" if activity != "stop" else "position_request"]
        cases.append({
            "case_id": case, "target_law_id": "NRS-484B-450-1h",
            "cell_id": "C150660", "actor": "motor_vehicle_driver",
            "target_type": "boundary_probe",
            "rationale": "Original Native safety-zone stop request; realized footprint, designation, curb and exceptions need independent source review.",
            "recording_description": DESCRIPTION,
            "unresolved_judgment_calls": [
                "Official safety-zone designation and adjacent curb status",
                "Actual stop/stand/park purpose and exception authority or necessity",
                "Physical stop location and actual four-view pixels"],
            "variable_assignments": {
                "position_request": {"kind": "controller", "value": position, "unit": "category"},
                "requested_curb_end_gap_ft": {"kind": "controller", "value": gap_ft, "unit": "ft"},
                "activity_request": {"kind": "controller", "value": activity, "unit": "category"},
                "exception_request": {"kind": "controller", "value": exception, "unit": "category"},
                "observed_zone_and_exception_state": {"kind": "subject_behavior", "value": None,
                                                      "unit": "structured"}},
            "paired_probe_id": ("c150660-" + ("curb-end-distance" if suffix.startswith(("end_", "start_")) else
                                                 "selected-pair" if suffix.startswith("selected_") else
                                                 suffix)),
            "deliberate_differences": differences,
            "probe": {
                "primary_variable": "requested_curb_end_gap_ft" if gap_ft is not None else
                                    "exception_request" if exception != "none" else
                                    "activity_request" if activity != "stop" else "position_request",
                "comparison_or_standard": "30 feet from either opposite curb-end point or between zone and curb",
                "target_value_or_branch": str(gap_ft) + " ft" if gap_ft is not None else
                                          position + "/" + activity + "/" + exception,
                "threshold_ref": "activation.numeric_conditions[0]" if suffix.startswith(("end_", "start_")) else None,
                "operator": "<=" if gap_ft is not None else "categorical",
                "unit": "ft" if gap_ft is not None else "category",
                "test_value": gap_ft if gap_ft is not None else
                              (exception if exception != "none" else activity if activity != "stop" else position)},
            **({"epsilon_used": "5 ft engineering probe spacing, not legal tolerance"}
               if gap_ft is not None else {})})
    proposal = {"format": "canonical-cases", "status": "draft",
                "cell_id": "C150660", "actor": "motor_vehicle_driver",
                "sweep_specs": [], "cases": cases}
    path = FOLDER / "proposals/cases.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proposal, indent=2) + "\n")
    return path


if __name__ == "__main__":
    print(build())
