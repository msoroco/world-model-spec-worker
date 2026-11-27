"""Bind provisional selected source recipes to the pinned public compatibility entrypoint."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSIGNMENT = ROOT.name
RUNTIME_SHA = "5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    entries, proposals = [], []
    for condition, controller in (("a", "distance_triggered_slow_request"),
                                  ("b", "maintain_request")):
        case_id = ASSIGNMENT + "__selected_90e3f1aa__condition_" + condition
        construction_path = HERE / ("selected-" + condition + "-construction.json")
        construction = json.loads(construction_path.read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        requirements = []
        for index, row in enumerate(plan["requirement_dispositions"]):
            if row["status"] != "selected_required" or case_id not in row["case_ids"]:
                continue
            method, key, kind, value_type, inputs = (
                ("measure_driver_source", "driver_source", "sourced_context", "text",
                 ["pedestrian-due-care-trace.jsonl", "road_survey.json"])
                if index == 0 else
                ("measure_pedestrian_encounter", "pedestrian_encounter_gap", "measured", "number",
                 ["pedestrian-due-care-trace.jsonl", "video_frames.jsonl",
                  "contact_events.jsonl", "road_survey.json"])
                if index == 1 else
                ("measure_person_afoot", "person_afoot_source", "sourced_context", "text",
                 ["road_survey.json", "pedestrian-due-care-trace.jsonl"]))
            requirements.append({"disposition_index": index, "requirement": row["requirement"],
                                 "source": row["source"], "output_key": key,
                                 "method": method, "value_type": value_type,
                                 "kind": kind, "inputs": inputs})
        contract_path = HERE / ("selected-" + condition + "-measurement-contract.json")
        write(contract_path, {"format": "worker-measurement-contract", "case_id": case_id,
                              "requirements": requirements,
                              "negative": {"remove": ["contact_events.jsonl"],
                                           "error_contains": "Missing required source: contact_events.jsonl"}})
        entries.append({"case_id": case_id, "kind": "delivery", "id": "primary",
                        "construction": "native/selected-" + condition + "-construction.json",
                        "construction_sha256": sha(construction_path),
                        "candidate_risk": {"status": "physical",
                                           "reason": "Native pedestrian path, actor response and camera framing require physical review"},
                        "candidates": [],
                        "measurement_contract": "native/" + contract_path.name,
                        "measurement_procedure": {"entrypoint": "finalize.py",
                                                  "status": "saved_source_diagnostic"},
                        "fixture_recipe": "work/" + ASSIGNMENT + "/native/selected-" + condition + "-fixture-recipe.json"})
        proposals.append({"case_id": case_id, "target_law_id": "NRS-484B-280-1a",
                          "target_type": "judgment_sweep",
                          "rationale": "Source-bound pedestrian encounter response contrast; due care remains unresolved",
                          "paired_probe_id": ASSIGNMENT + "__selected_90e3f1aa__comparison",
                          "deliberate_differences": ["pedestrian_conflict_response"],
                          "probe": {"primary_variable": "pedestrian_conflict_response",
                                    "comparison_or_standard": "requested vehicle response near person afoot",
                                    "target_value_or_branch": controller},
                          "variable_assignments": {
                              "pedestrian_conflict_response": {"kind": "controller", "value": controller,
                                                               "unit": "categorical"}},
                          "unresolved_judgment_calls": ["Exercise due care to avoid a collision with a pedestrian."],
                          "recording_description": config["recording_description"]})
    write(ROOT / "proposals/cases.json", {"cell_id": "C230266", "actor": "motor_vehicle_driver",
                                          "status": "provisional_public_compatibility_only",
                                          "sweep_specs": [], "cases": proposals})
    manifest_path = ROOT / "selected-compat-manifest.json"
    write(manifest_path, {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                          "runtime_manifest_sha256": RUNTIME_SHA,
                          "status": "provisional_public_compatibility_only", "cases": entries})
    print(json.dumps({"manifest_sha256": sha(manifest_path),
                      "cases": [{"case_id": e["case_id"],
                                 "contract_sha256": sha(ROOT / e["measurement_contract"])}
                                for e in entries]}))


if __name__ == "__main__":
    main()
