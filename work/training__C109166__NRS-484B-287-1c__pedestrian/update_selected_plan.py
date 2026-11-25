"""Bind selected crossing cases while preserving exact frozen law and evidence."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "case-plan.json"
ASSIGNMENT = HERE.name


def update():
    plan = json.loads(PLAN.read_text())
    law = json.loads((HERE.parents[1] / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    if plan["source_law_text"] != law["law"]["text"]:
        raise ValueError("Exact law text changed")
    case_ids = [case["case_id"] for case in plan["cases"]]
    if case_ids != [ASSIGNMENT + "__marked_crosswalk", ASSIGNMENT + "__unmarked_midblock"]:
        raise ValueError("Exact comparison cases changed")
    for case in plan["cases"]:
        case.update(selected=True, planning_status="selected_cpu_draft",
                    kind="delivery", selection_status="selected",
                    selection_targets=["full-train"],
                    requested_not_measured=True, expected_label=None,
                    gap_ids=["no-accepted-original"])
    for disposition in plan["requirement_dispositions"]:
        disposition["status"] = "selected_required"
        disposition["case_ids"] = case_ids
        if disposition["requirement"] == "text-1":
            disposition["evidence_or_gap"] = (
                "NRS 484B.290 is referenced but its exact operative text and person-specific "
                "applicability are absent from frozen sources; source-bound CPU analysis retains "
                "undetermined status for independent local review.")
    plan["evidence_review"] = {
        "method": "frozen accepted-recording inventory and membership review",
        "reviewer": "worker CPU preparation",
        "facts": [],
        "gaps": [{"id": "no-accepted-original", "requirement": "NRS-484B-287-1c",
                  "source": "inputs/" + ASSIGNMENT + "/assignment.json",
                  "why_existing_insufficient": "No accepted full-train membership or reviewed recording supplied"}]}
    mapping = {
        "ru.subject": ("ru.subject", ["pedestrian-original.jsonl"]),
        "st.intersection": ("st.intersection", ["native-survey.json", "trace.jsonl"]),
        "st.lane_enters": ("st.lane_enters", ["native-survey.json", "road.xodr"]),
        "dev.traffic_signal": ("dev.traffic_signal", ["controls-original.jsonl", "native-survey.json"]),
        "st.crosswalk": ("st.crosswalk", ["native-survey.json", "native-survey-media/marking.txt"]),
        "rel.occupies": ("rel.occupies", ["pedestrian-original.jsonl"]),
        "st.roadway": ("st.roadway", ["native-survey.json", "pedestrian-original.jsonl"]),
        "kin.position": ("kin.position", ["pedestrian-original.jsonl"]),
    }
    for term, (channel, sources) in mapping.items():
        plan["source_observation_mapping"][term] = {
            "evidence": "Original Native source-bound channel with independent physical review pending",
            "channels": [channel], "source_refs": sources}
    plan["runtime_uncertainties"] = [
        "Selected candidate constructions and exact offline CPU tests pass; Native physical realization remains unobserved.",
        "Original map/device survey, actual camera visibility and NRS 484B.290 person-specific applicability require independent local review.",
        "Public compatibility, saved-only processing and independent audits remain in progress."]
    PLAN.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"selected_cases": case_ids, "dispositions": len(plan["requirement_dispositions"])}))


if __name__ == "__main__":
    update()
