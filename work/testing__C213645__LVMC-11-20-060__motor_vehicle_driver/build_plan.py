"""Materialize the reviewed exact-case plan for the residential driveway cell."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "case-plan.json"
BASE = json.loads(PLAN.read_text())
AID = BASE["assignment_id"]
SOURCE = next(x for x in BASE["sources"] if x["path"].endswith("/assignment.json"))

variants = [
    ("sidewalk_stop", "stop_before_sidewalk", "halt_before_sidewalk", "pedestrian_absent", "roadway_clear"),
    ("sidewalk_roll", "roll_across_sidewalk", "moving_at_sidewalk", "pedestrian_absent", "roadway_clear"),
    ("pedestrian_yield", "stop_before_sidewalk", "halt_before_sidewalk", "pedestrian_crossing_yield", "roadway_clear"),
    ("pedestrian_intrude", "stop_before_sidewalk", "halt_before_sidewalk", "pedestrian_crossing_intrude", "roadway_clear"),
    ("roadway_left_yield", "stop_before_sidewalk", "halt_before_sidewalk", "pedestrian_absent", "left_approach_yield"),
    ("roadway_left_intrude", "stop_before_sidewalk", "halt_before_sidewalk", "pedestrian_absent", "left_approach_intrude"),
    ("roadway_right_yield", "stop_before_sidewalk", "halt_before_sidewalk", "pedestrian_absent", "right_approach_yield"),
    ("roadway_right_intrude", "stop_before_sidewalk", "halt_before_sidewalk", "pedestrian_absent", "right_approach_intrude"),
]
common = [
    "same residence-district frontage and same private driveway crossing a sidewalk before a connected two-direction roadway",
    "same ego motor vehicle, entry path and body clearance, controller gains, weather, 20 Hz duration, and synchronized four-view cameras",
    "same sidewalk and roadway boundary survey; no assumed crosswalk, traffic device, or controlled-access entrance",
    "same inactive participant policy except the deliberately varied pedestrian or approaching roadway vehicle",
]
cases = []
for name, command, stop, pedestrian, road in variants:
    cases.append({
        "case_id": AID + "__" + name,
        "target_law_id": BASE["law_id"],
        "branch": "Residential driveway roadway entry",
        "kind": "delivery",
        "gap_ids": ["no-accepted-original-driveway-entry"],
        "world_setup": {
            "district": "residence", "access": "private_driveway", "sidewalk": "intervening_sidewalk_area",
            "roadway": "connected_two_direction_road", "pedestrian": pedestrian,
            "roadway_vehicle": road,
        },
        "controller": {"entry_behavior": command, "stop_target": stop},
        "subject_behavior": {"realized_stop": None, "realized_pedestrian_precedence": None,
                             "realized_roadway_precedence": None},
        "fixed_conditions": common,
        "deliberate_condition": f"{command}; {pedestrian}; {road}",
        "measurement": "original frame-joined ego velocity, body polygons, sidewalk/roadway boundary survey, pedestrian and roadway-vehicle activity and precedence",
        "legal_judgment": "unverified; immediately-prior, necessary-to-avoid-collision, and right-of-way remain for independent review",
        "candidate_risk": {"status": "physical", "reason": "The surveyed driveway-to-sidewalk-to-roadway path and participant clearance may be disrupted by a local CARLA map or collision placement; retain a same-law/camera/duration fallback with a measurable clearance trigger."},
        "planned_original_capture": True,
    })

def comparison(name, left, right, difference):
    return {
        "comparison_id": name,
        "case_ids": [AID + "__" + left, AID + "__" + right],
        "fixed_conditions": common,
        "deliberate_differences": [difference],
        "audit_rule": "Compare actual original activity and geometry; reject a changed district, route, boundary, participants or camera contract outside the declared difference. Do not infer a legal verdict from intended controller settings.",
    }

BASE["cases"] = cases
BASE["comparisons"] = [
    comparison("stop_before_sidewalk", "sidewalk_stop", "sidewalk_roll", "ego stop versus roll request immediately before the sidewalk boundary"),
    comparison("pedestrian_precedence", "pedestrian_yield", "pedestrian_intrude", "ego crossing time relative to the same moving pedestrian"),
    comparison("left_roadway_precedence", "roadway_left_yield", "roadway_left_intrude", "ego road-entry time relative to the same left-approaching roadway vehicle"),
    comparison("right_roadway_precedence", "roadway_right_yield", "roadway_right_intrude", "ego road-entry time relative to the same right-approaching roadway vehicle"),
]
BASE["observations"] = [
    {"name": "driver_and_district_context", "mandatory": True, "source": "original reviewed jurisdiction, frontage, actor and vehicle provenance"},
    {"name": "driveway_sidewalk_roadway_geometry", "mandatory": True, "source": "original native route and surveyed region polygons"},
    {"name": "ego_motion_and_body", "mandatory": True, "source": "original 20 Hz ego kinematics and body polygon"},
    {"name": "pedestrian_motion_and_body", "mandatory": True, "source": "original 20 Hz pedestrian activity in selected pedestrian cases"},
    {"name": "approaching_vehicle_motion_and_body", "mandatory": True, "source": "original 20 Hz roadway vehicle activity in selected roadway cases"},
    {"name": "frame_map_and_cameras", "mandatory": True, "source": "original synchronized Native frame map and four videos"},
]
BASE["selected_branch"] = BASE["selected_branches"][0]
BASE["requirement_dispositions"] = [
    {
        "requirement": text,
        "source": SOURCE,
        "status": "selected_required",
        "case_ids": [c["case_id"] for c in cases],
        "evidence_or_gap": "No accepted original recording in frozen evidence.json; exact original capture and independent review required.",
        "disposition_index": i,
    }
    for i, text in enumerate([
        "LVMC 11.20.060 applies to a vehicle driver in a business or residence district emerging or entering an alley, driveway or building; selected branch fixes residence district and driveway.",
        "Stop immediately before driving onto the sidewalk or sidewalk area extending across the driveway.",
        "Yield to any pedestrian as necessary to avoid collision during sidewalk crossing.",
        "Upon entering roadway yield to all vehicles approaching on that roadway, including both travel approaches in the selected two-direction road.",
    ])
]
BASE["evidence_review"]["gaps"] = [{
    "id": "no-accepted-original-driveway-entry",
    "requirement": "Residence-district driveway, sidewalk stop, pedestrian and roadway vehicle precedence",
    "source": SOURCE,
    "why_existing_insufficient": "Frozen evidence.json lists no accepted recordings for this assignment.",
}]
BASE["runtime_uncertainties"] = [
    "Physical district frontage, driveway connection, sidewalk geometry, participant motion and camera coverage require original local CARLA verification.",
    "Fixture measurements are software diagnostics; immediately prior, collision-avoidance necessity and right-of-way are not resolved by a worker-provided numeric cutoff.",
]
BASE["source_observation_mapping"] = {}
BASE["camera_plan"] = {
    "profile": "overview1080-capability", "duration_s": 45,
    "composition": "synchronized_four_view_primary",
    "coverage": [
        {"view": "overview", "subject": "residential frontage, private driveway, sidewalk and roadway approaches", "interval": "full 45 second original episode"},
        {"view": "approach", "subject": "ego approach and full stop immediately before sidewalk crossing", "interval": "full 45 second original episode"},
        {"view": "reference_corner", "subject": "sidewalk boundary, pedestrian and ego body clearance", "interval": "full 45 second original episode"},
        {"view": "driver_reference", "subject": "ego road entry and both approaching roadway directions", "interval": "full 45 second original episode"},
    ],
}
BASE["planning_status"] = "exact_cases_selected_cpu_construction_in_progress"
PLAN.write_text(json.dumps(BASE, indent=2) + "\n")
