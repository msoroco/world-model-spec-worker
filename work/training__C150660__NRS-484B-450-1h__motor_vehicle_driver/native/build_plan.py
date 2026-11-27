"""Bind the statutory alternatives to exact planned Native requests."""

import json
from pathlib import Path

from case_specs import CASES

FOLDER = Path(__file__).resolve().parents[1]
ASSIGNMENT = FOLDER.name
LAW = "NRS-484B-450-1h"
SOURCE = "inputs/training__C150660__NRS-484B-450-1h__motor_vehicle_driver/assignment.json"
TEXT = ("A person shall not stop, stand or park a vehicle, except when necessary "
        "to avoid conflict with other traffic or in compliance with law or the "
        "directions of a police officer or official traffic-control device, in "
        "any of the following places: Between a safety zone and the adjacent "
        "curb or within 30 feet of points on the curb immediately opposite the "
        "ends of a safety zone.")
CAMERA_PLAN = {"profile": "overview1080-capability", "duration_s": 30,
               "composition": "synchronized_four_view_primary",
               "coverage": [
                   {"subject": "safety zone, curb and both opposite end points",
                    "interval": "all 600 frames", "view": "overview"},
                   {"subject": "approaching and resting ego body",
                    "interval": "all 600 frames", "view": "approach"},
                   {"subject": "curb-end reference and zone edge markers",
                    "interval": "all 600 frames", "view": "reference_corner"},
                   {"subject": "driver approach and contextual traffic/device actors",
                    "interval": "all 600 frames", "view": "driver_reference"}]}


def cid(suffix):
    return ASSIGNMENT + "__" + suffix


def comparison(name, suffixes, difference):
    return {"comparison_id": ASSIGNMENT + "__" + name,
            "case_ids": [cid(suffix) for suffix in suffixes],
            "deliberate_differences": [difference],
            "fixed_conditions": [
                "same authored C150660 one-way road, shoulder, refuge and curb source plan",
                "same motor vehicle actor and 600-frame 20 Hz four-camera acquisition",
                "same stop controller and context except named position, activity or exception request",
                "original safety-zone designation, curb and exception status independently reviewed"],
            "status": "selected_pending_original_source_measurement",
            "measurement_method": "Measure original stopped vehicle footprint against both opposite curb-end points and zone/curb band."}


def build():
    plan = json.loads((FOLDER / "case-plan.json").read_text())
    plan["source_law_text"] = TEXT
    plan["source_law_citation"] = "NRS 484B.450(1)(h)"
    plan["scope_branches"] = [
        "between established safety zone and adjacent curb",
        "within 30 feet of each point on curb opposite zone ends",
        "stop, stand and park activity alternatives",
        "traffic-conflict, law, officer and device exceptions, independently reviewed"]
    plan["camera_plan"] = CAMERA_PLAN
    all_ids = [cid(suffix) for suffix in CASES]
    for disposition in plan["requirement_dispositions"]:
        disposition["status"] = "selected_required"
        disposition["case_ids"] = all_ids
        disposition["evidence_or_gap"] = (
            "Selected exact-case Native construction, original geometry and source-reviewed "
            "designation/exception context; no physical or legal outcome inferred from requests.")
    plan["cases"] = []
    for suffix, (position, activity, exception, gap_ft) in CASES.items():
        description = (f"Original Native {activity} request {position} relative to the "
                       f"authored refuge; curb-end request {gap_ft} ft; exception "
                       f"request {exception}. Realized footprint and authority need review.")
        plan["cases"].append({
            "case_id": cid(suffix), "target_law_id": LAW,
            "target_type": "boundary_probe" if gap_ft is not None else "controlled_branch_probe",
            "planning_status": "selected_pending_original_source_review",
            "source_branch": plan["selected_branch"],
            "comparison_variable": ("curb_end_footprint_distance" if gap_ft is not None else
                                    "activity_or_exception_or_zone_position"),
            "comparison_unit": "ft" if gap_ft is not None else "source-reviewed category",
            "requested_setting": gap_ft,
            "recorded_value": None, "case_description": description,
            "source_topic_ids": ["text-0", "text-1", "reviewed-scope-0"],
            "selected": True, "selection_reason": description,
            "camera_plan": {"duration_seconds": 30, "fps": 20, "frames": 600,
                            "cameras": ["overview", "approach", "reference_corner", "driver_reference"]},
            "position_request": position, "activity_request": activity,
            "exception_request": exception,
            "fixed_conditions": {"cell_id": "C150660", "layout": "one_way_road",
                                 "maneuver": "stop_stand", "control": "safety_zone",
                                 "actor": "motor_vehicle_driver", "law_id": LAW,
                                 "selection_targets": ["full-train"]},
            "gap_ids": ["original-safety-zone-and-curb"]})
    plan["comparisons"] = [
        comparison("between_vs_outside", ("selected_6214a61f__condition_a",
                                          "selected_6214a61f__condition_b"),
                   "requested resting footprint between zone/curb versus beyond both end bands"),
        comparison("end_boundary", ("end_25", "end_30", "end_35"),
                   "requested distance 25/30/35 ft from curb point opposite downstream zone end"),
        comparison("start_boundary", ("start_25", "start_30", "start_35"),
                   "requested distance 25/30/35 ft from curb point opposite upstream zone end"),
        comparison("stop_stand_park", ("selected_6214a61f__condition_a", "stand_between", "park_between"),
                   "requested stop versus stand versus park activity"),
    ]
    for exception in ("conflict", "law", "officer", "device"):
        plan["comparisons"].append(comparison(
            exception + "_exception",
            ("selected_6214a61f__condition_a", exception + "_between"),
            "requested " + exception + " exception context; authority and necessity need original review"))
    plan["observations"] = [{"name": name, "mandatory": True,
                             "source_note": note, "status": "native_source_and_saved_measurement"}
                            for name, note in (
                                ("drv.standing_or_parked", "Native speed and halt request"),
                                ("st.safety_zone", "authored/map zone plus independent designation"),
                                ("st.road_edge", "Native curb plus source review"),
                                ("rel.occupies", "stopped footprint between zone and curb"),
                                ("rel.centre_distance", "footprint to both opposite curb-end points"),
                                ("kin.position", "four-corner Native footprint and curb points"),
                                ("drv.forced_halt", "traffic necessity and halt purpose review"),
                                ("dev.human_direction", "officer direction review"),
                                ("exception_context", "law and device direction review"))]
    plan["source_observation_mapping"] = {
        name: {"evidence": "Original zone_raw.json and context-survey.json; synthetic diagnostic is software proof only",
               "channels": [name], "source_refs": [SOURCE, "native/runner.py", "native/finalize.py"]}
        for name in ("drv.standing_or_parked", "st.safety_zone", "st.road_edge",
                     "rel.occupies", "rel.centre_distance", "kin.position",
                     "drv.forced_halt", "dev.human_direction")}
    plan["evidence_review"] = {"reviewer": "worker CPU source review",
                               "method": "Frozen assignment lists no accepted membership or evidence inventory; all original source requirements remain new.",
                               "facts": [], "gaps": [{"id": "original-safety-zone-and-curb",
                                                     "requirement": "Original zone/curb, stopped footprint and exceptions",
                                                     "source": SOURCE,
                                                     "why_existing_insufficient": "No accepted recording is listed for this assignment."}]}
    plan["runtime_uncertainties"] = [
        "Original map and independent review must establish the safety zone and adjacent curb",
        "Requested 25/30/35 ft probes are not observed distances or legal verdicts",
        "Original traffic-conflict, law, officer and device authority/necessity require separate review",
        "Actual motion, four-view pixels and physical completion remain unverified"]
    plan["readiness"] = "selected_pending_cpu_delivery_proofs"
    (FOLDER / "case-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan


if __name__ == "__main__":
    plan = build()
    print(len(plan["cases"]), len(plan["comparisons"]))
