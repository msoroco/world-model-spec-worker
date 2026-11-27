"""Draft canonical selected pair without asserting a legal outcome."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def build():
    construction = json.loads((ROOT / "construction.json").read_text())
    recording = construction["recording_description"]
    common = {"obstruction_kind": {"kind": "world_setup", "value": "physical_obstruction",
                                   "unit": "category"},
              "park_y_m": {"kind": "controller", "value": None, "unit": "m"},
              "police_direction_source_request": {"kind": "controller", "value": 0,
                                                    "unit": "category"},
              "observed_open_width_m": {"kind": "subject_behavior", "value": None,
                                        "unit": "m"},
              "observed_passing_response": {"kind": "subject_behavior", "value": None,
                                            "unit": "structured"}}
    baseline = {"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
                "target_type": "baseline", "cell_id": "C135702",
                "actor": "motor_vehicle_driver",
                "rationale": "Unselected common narrow-highway and driver context.",
                "variable_assignments": common, "recording_description": recording,
                "unresolved_judgment_calls": []}
    cases = [baseline]
    for suffix, y, intent in (("a", -1.1, "narrower"), ("b", -2.5, "wider")):
        assignments = json.loads(json.dumps(common))
        assignments["park_y_m"]["value"] = y
        cases.append({"case_id": ASSIGNMENT + "__selected_dacdf461__condition_" + suffix,
                      "target_law_id": "NRS-484B-450-1k",
                      "target_type": "boundary_probe",
                      "cell_id": "C135702", "actor": "motor_vehicle_driver",
                      "rationale": "Authored " + intent + " physical opening for measurement contrast; legal classification unverified.",
                      "variable_assignments": assignments,
                      "recording_description": recording,
                      "unresolved_judgment_calls": [
                          "when stopping, standing or parking would obstruct traffic",
                          "except when necessary to avoid conflict with other traffic",
                          "in compliance with law",
                          "the directions of a police officer",
                          "official traffic-control device"],
                      "paired_probe_id": "park_obstruction_opening",
                      "deliberate_differences": ["park_y_m"],
                      "probe": {"primary_variable": "park_y_m",
                                "comparison_or_standard": "same road and physical obstruction with two parked positions",
                                "target_value_or_branch": intent}})
    selected_cases = json.loads(json.dumps(cases))
    for suffix, request in (("police_absent", 0), ("police_present", 1)):
        assignments = json.loads(json.dumps(common))
        assignments["park_y_m"]["value"] = -1.1
        assignments["police_direction_source_request"]["value"] = request
        cases.append({"case_id": ASSIGNMENT + "__selected_police_source__" + suffix,
                      "target_law_id": "NRS-484B-450-1k", "target_type": "boundary_probe",
                      "cell_id": "C135702", "actor": "motor_vehicle_driver",
                      "rationale": "Source-gated police-direction request contrast with fixed physical scene; applicability unverified.",
                      "variable_assignments": assignments,
                      "recording_description": recording,
                      "unresolved_judgment_calls": [
                          "when stopping, standing or parking would obstruct traffic",
                          "except when necessary to avoid conflict with other traffic",
                          "in compliance with law",
                          "the directions of a police officer",
                          "official traffic-control device"],
                      "paired_probe_id": "police_source_branch",
                      "deliberate_differences": ["police_direction_source_request"],
                      "probe": {"primary_variable": "police_direction_source_request",
                                "comparison_or_standard": "same physical road, obstruction and parked body with original police source request varied",
                                "target_value_or_branch": "present" if request else "absent"}})
    result = {"cell_id": "C135702", "actor": "motor_vehicle_driver",
              "status": "draft", "sweeps_expanded": True,
              "cases": selected_cases, "sweep_specs": []}
    path = ROOT / "proposals/cases.json"
    path.parent.mkdir(exist_ok=True)
    if path.is_file():
        result["sweep_specs"] = json.loads(path.read_text()).get("sweep_specs", [])
    path.write_text(json.dumps(result, indent=2) + "\n")
    police_draft = dict(result, cases=cases)
    (ROOT / "proposals/police-cases-draft.json").write_text(
        json.dumps(police_draft, indent=2) + "\n")


if __name__ == "__main__":
    build()
