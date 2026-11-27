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
                      "unresolved_judgment_calls": ["whether stopping, standing or parking would obstruct traffic",
                                                    "applicability of each source exception"],
                      "paired_probe_id": "park_obstruction_opening",
                      "deliberate_differences": ["park_y_m"],
                      "probe": {"primary_variable": "park_y_m",
                                "comparison_or_standard": "same road and physical obstruction with two parked positions",
                                "target_value_or_branch": intent}})
    result = {"cell_id": "C135702", "actor": "motor_vehicle_driver",
              "status": "draft", "sweeps_expanded": True,
              "cases": cases, "sweep_specs": []}
    path = ROOT / "proposals/cases.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    build()
