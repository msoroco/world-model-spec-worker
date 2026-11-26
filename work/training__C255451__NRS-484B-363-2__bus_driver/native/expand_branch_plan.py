"""Expand the finite school-crossing exception plan without selecting drafts."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AID = ROOT.name
PREFIX = AID + "__selected_d08892c9__"
CONDITIONS = [
    "condition_a", "condition_b", "at_limit", "no_school_day",
    "half_hour_window", "beacon_not_flashing",
    "nonbeacon_sign_active", "nonbeacon_sign_inactive",
]
PAIRS = {
    "speed_boundary": ("condition_a", "at_limit", "condition_b"),
    "no_school_day": ("condition_b", "no_school_day"),
    "half_hour_window": ("condition_b", "half_hour_window"),
    "beacon_flash": ("condition_b", "beacon_not_flashing"),
    "nonbeacon_sign": ("nonbeacon_sign_active", "nonbeacon_sign_inactive"),
}
DIFFERENCES = {
    "speed_boundary": "measured motor-bus speed below, at and above express 25 mph",
    "no_school_day": "independently reviewed school-session day status",
    "half_hour_window": "independently reviewed civil time relative to school operating hours",
    "beacon_flash": "observed alternating yellow-light flash during pupils-in-class hours",
    "nonbeacon_sign": "independently reviewed sign effective-hours indication without operational beacon",
}
TOPIC_CASES = {
    "text-0": CONDITIONS,
    "text-1": ["condition_b", "no_school_day"],
    "text-2": ["condition_b", "half_hour_window"],
    "text-3": ["condition_b", "beacon_not_flashing"],
    "text-4": ["nonbeacon_sign_active", "nonbeacon_sign_inactive"],
    "text-5": ["condition_b", "beacon_not_flashing"],
    "reviewed-scope-0": CONDITIONS,
}


def main():
    path = ROOT / "case-plan.json"
    plan = json.loads(path.read_text())
    first = plan["cases"][0]
    cases = []
    for condition in CONDITIONS:
        case = dict(first)
        case["case_id"] = PREFIX + condition
        case["condition_index"] = CONDITIONS.index(condition)
        case["comparison_variable"] = (
            "measured_bus_speed" if condition in ("condition_a", "condition_b", "at_limit")
            else "reviewed_school_exception_source")
        case["target_type"] = "planned_delivery_branch"
        case["planning_status"] = "unselected_offline_draft"
        case["planned_context"] = condition
        case["source_requirements"] = [
            "original motor-bus class and velocity", "official school-crossing-zone designation",
            "installed zone sign and road boundaries", "school calendar and operating hours",
            "timezone-aware civil clock", "operational beacon presence and alternating-yellow pixels",
            "nonbeacon sign effective-hours indication", "original child actor and camera evidence",
        ]
        case["gap_ids"] = ["no_accepted_original_evidence"]
        cases.append(case)
    plan["cases"] = cases
    plan["comparisons"] = [{
        "comparison_id": PREFIX + key,
        "case_ids": [PREFIX + name for name in pair],
        "deliberate_differences": [DIFFERENCES[key]],
        "fixed_conditions": [
            "C255451 school-crossing layout, bus actor class, road direction and zone geometry",
            "600 frames at 20 Hz with four named original cameras",
            "all source conditions except the declared difference",
        ],
        "status": "planned_unselected",
        "audit_gap": "Independent source-bound comparison audit not yet implemented",
    } for key, pair in PAIRS.items()]
    for disp in plan["requirement_dispositions"]:
        topic = disp["requirement"]
        disp["case_ids"] = [PREFIX + name for name in TOPIC_CASES[topic]]
        disp["status"] = "planned_required"
        disp["evidence_or_gap"] = (
            "Finite source-backed delivery plan; original acquisition and independent CPU proofs remain pending.")
    plan["evidence_review"] = {
        "reviewer": "worker CPU source review",
        "method": "No accepted recording or membership row in frozen assignment; no evidence reuse inferred.",
        "facts": [],
        "gaps": [{
            "id": "no_accepted_original_evidence",
            "requirement": "Original zone, bus, sign, civil-time and exception sources",
            "source": "inputs/" + AID + "/assignment.json",
            "why_existing_insufficient": "Frozen selection has no accepted member or recording to review.",
        }],
    }
    plan["readiness"] = "eight_unselected_offline_drafts"
    plan["legal_analysis_note"] = (
        "25 mph is the express threshold. School day, half-hour window, operational "
        "beacon with alternating yellow lights, and nonbeacon sign schedule are "
        "separate source-required exception branches; authored contexts assert no legal outcome.")
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"cases": len(cases), "comparisons": len(plan["comparisons"])}))


if __name__ == "__main__":
    main()
