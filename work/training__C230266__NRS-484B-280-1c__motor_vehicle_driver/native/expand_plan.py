"""Expand the frozen pedestrian-caution text into exact controlled case pairs."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ASSIGNMENT = ROOT.name
LAW = "NRS-484B-280-1c"
SOURCE = "NRS 484B.280(1)(c)"


BRANCHES = (
    ("road", "Pedestrian on or near a highway, street or road.", "roadway boundary and pedestrian body position"),
    ("transit_stop", "Pedestrian at or near a bus stop, bench, shelter or transit stop.", "original stop furniture and transit designation"),
    ("boarding", "Pedestrian in the act of boarding a bus or other public transportation vehicle.", "vehicle class, door side and continuous boarding movement"),
    ("school_zone", "Pedestrian in or near a school zone marked under NRS 484B.363.", "original school-zone sign and governed extent"),
    ("school_crossing", "Pedestrian in or near a school crossing zone marked under NRS 484B.363.", "original school-crossing-zone sign and governed extent"),
    ("marked_crosswalk", "Pedestrian in or near a marked crosswalk.", "original visible markings and roadway location"),
    ("unmarked_crosswalk", "Pedestrian in or near an unmarked crosswalk.", "original intersection, sidewalk alignment and crossing limits"),
)


def case_id(branch, mode):
    if branch == "road":
        return f"{ASSIGNMENT}__probe_{1 if mode == 'caution' else 2}"
    return f"{ASSIGNMENT}__{branch}_{mode}"


def main():
    path = ROOT / "case-plan.json"
    plan = json.loads(path.read_text())
    cases = []
    comparisons = []
    dispositions = []
    for index, (branch, text, source) in enumerate(BRANCHES):
        ids = [case_id(branch, mode) for mode in ("caution", "maintain")]
        for mode, cid in zip(("caution", "maintain"), ids):
            cases.append({
                "case_id": cid, "target_law_id": LAW, "kind": "planned_only",
                "target_type": "controlled_attempt", "source_branch": text,
                "physical_target": f"{branch}: observed driver {'slows' if mode == 'caution' else 'maintains approach request'} after a sourced pedestrian observation",
                "comparison_variable": "post_observation_ego_speed_request",
                "source_survey_required": source,
                "requested_not_measured": True, "selection_targets": ["full-train"],
                "gap_ids": [f"gap-{branch}"]})
        comparisons.append({
            "comparison_id": f"{ASSIGNMENT}__{branch}_comparison",
            "case_ids": ids, "deliberate_differences": ["post_observation_ego_speed_request"],
            "fixed_conditions": ["C230266 road/travel/pedestrian cell and motor-vehicle driver",
                                 "same source-surveyed pedestrian location and path",
                                 "same approach, visibility and actual-observation review protocol",
                                 "same 600-frame 20-Hz four-camera capture profile"],
            "source_branch": text})
        dispositions.append({
            "disposition_index": index, "requirement": LAW, "source": SOURCE,
            "branch": text, "status": "selected_required", "case_ids": ids,
            "evidence_or_gap": f"No accepted source-backed recording; selected controlled pair needs original {source}. Physical and legal outcomes unverified."})
    plan["cases"] = cases
    plan["comparisons"] = comparisons
    plan["requirement_dispositions"] = dispositions
    plan["selected_branch"] = "Pedestrian on or near a highway, street or road."
    plan["evidence_review"] = {
        "reviewer": "worker owner", "method": "Read the frozen assignment, witnesses and absence of accepted full-train membership; did not infer evidence from an empty membership list.",
        "facts": [],
        "gaps": [{"id": f"gap-{branch}", "requirement": text, "source": SOURCE,
                  "why_existing_insufficient": "No accepted recording or original physical source inventory was supplied."}
                 for branch, text, _ in BRANCHES]}
    plan["camera_plan"] = {
        "profile": "overview1080-capability", "duration_s": 30,
        "composition": "synchronized_four_view_primary",
        "coverage": [{"view": view, "subject": subject, "interval": "frames 0-599"}
                     for view, subject in (("overview", "ego/pedestrian and roadway context"),
                                           ("approach", "pedestrian and roadway approach"),
                                           ("reference_corner", "stop, zone or crossing reference"),
                                           ("driver_reference", "driver-eye proxy and pedestrian line of sight"))]}
    channels = {entry["term"]: {"evidence": entry["evidence"],
                               "channels": entry["channels"], "source_refs": entry["source_refs"]}
                for entry in plan["source_observation_mapping"]}
    plan["source_observation_mapping"] = channels
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"cases": len(cases), "comparisons": len(comparisons)}))


if __name__ == "__main__":
    main()
