"""Bounded controller requests for selected left-lane/HOV encounters."""

import json
from pathlib import Path

from package_contract import ASSIGNMENT, LAW


HERE = Path(__file__).resolve().parent


def selected_schedule(case_id, posted_limit_mps):
    if not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact selected C380107 case required")
    proposal = json.loads((HERE / "proposals/cases.json").read_text(encoding="utf-8"))
    selected = [c for c in proposal["cases"] if c.get("case_id") == case_id and c.get("target_law_id") == LAW]
    if len(selected) != 1:
        raise ValueError("case absent from selected canonical proposal")
    case = selected[0]
    assignments = case.get("variable_assignments", {})
    def value(name, default):
        return assignments.get(name, {}).get("value", default)
    if not isinstance(posted_limit_mps, (int, float)) or posted_limit_mps <= 0:
        raise ValueError("original positive posted limit required")
    speed_request = value("ego_speed_request", "below")
    rear_request = value("rear_encounter_request", "faster_same_left")
    response = value("ego_response_request", "remain_left")
    if speed_request not in ("below", "at_limit") or rear_request not in ("faster_same_left", "same_speed_rear"):
        raise ValueError("unsupported speed/encounter controller request")
    if response not in ("remain_left", "move_right"):
        raise ValueError("unsupported lane response controller request")
    delta = value("rear_speed_delta_target_mps", 2.0)
    onset = value("sign_exposure_start_s", 6.0)
    occupancy = value("hov_occupancy_target", 2)
    if not isinstance(delta, (int, float)) or not 0.5 <= delta <= 5:
        raise ValueError("rear approach request outside bounded engineering range")
    if not isinstance(onset, (int, float)) or not 0 <= onset <= 12:
        raise ValueError("sign onset request outside bounded engineering range")
    if not isinstance(occupancy, int) or not 1 <= occupancy <= 4:
        raise ValueError("occupancy request outside bounded engineering range")
    ego = posted_limit_mps if speed_request == "at_limit" else max(2.0, posted_limit_mps - 3.0)
    rear = ego if rear_request == "same_speed_rear" else ego + float(delta)
    return {"case_id": case_id, "ego_target_speed_mps": ego,
            "rear_target_speed_mps": rear, "ego_response_request": response,
            "sign_exposure_start_frame": round(20 * onset),
            "hov_occupancy_target": occupancy,
            "hov_designation_request": value("hov_designation_request", "none"),
            "hov_compliance_request": value("hov_compliance_request", "unresolved"),
            "exception_context_request": value("exception_context_request", "outside_city"),
            "legal_judgment": "unresolved"}
