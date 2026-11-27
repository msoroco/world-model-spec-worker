"""Draft canonical case proposals for the fixed safety-zone cell."""

import json
from pathlib import Path

from case_specs import CASES
from build_construction import DESCRIPTION

FOLDER = Path(__file__).resolve().parents[1]


def build():
    cases = []
    for suffix, (position, activity, exception, gap_ft) in CASES.items():
        case = FOLDER.name + "__" + suffix
        cases.append({
            "case_id": case, "target_law_id": "NRS-484B-450-1h",
            "target_type": "boundary_probe" if gap_ft is not None else "controlled_branch_probe",
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
                                                      "unit": "structured"}}})
    proposal = {"format": "canonical-cases", "status": "draft",
                "cell_id": "C150660", "actor": "motor_vehicle_driver",
                "sweep_specs": [], "cases": cases}
    path = FOLDER / "proposals/cases.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proposal, indent=2) + "\n")
    return path


if __name__ == "__main__":
    print(build())
