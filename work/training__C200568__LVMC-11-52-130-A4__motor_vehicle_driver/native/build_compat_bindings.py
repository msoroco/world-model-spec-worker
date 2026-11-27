"""Bind fourteen selected measurements to public fixture recipes."""

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
    plan_path = ROOT / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    for row in plan["requirement_dispositions"]:
        row["status"] = "selected_required"
        row["evidence_or_gap"] = ("Case-specific source-bound CPU construction and saved "
            "geometry diagnostic exist; original Native, exception provenance, "
            "physical completion and legal outcome remain unverified.")
    write(plan_path, plan)
    entries, proposals = [], []
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.split("__")[-1]
        construction_path = HERE / ("selected-" + suffix + "-construction.json")
        construction = json.loads(construction_path.read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        disposition_index = next(i for i, row in enumerate(plan["requirement_dispositions"])
                                 if case_id in row["case_ids"])
        branch = plan["requirement_dispositions"][disposition_index]
        exception = suffix.startswith("exception_")
        method = "measure_exception_context" if exception else "measure_hydrant_clearance"
        key = "exception_context" if exception else "hydrant_clearance_ft"
        sources = (["hydrant-trace.jsonl", "hydrant_survey.json"] if exception else
                   ["hydrant-trace.jsonl", "video_frames.jsonl", "hydrant_survey.json"])
        requirement = {"disposition_index": disposition_index,
                       "requirement": branch["requirement"], "source": branch["source"],
                       "output_key": key, "method": method,
                       "value_type": "text" if exception else "number",
                       "kind": "sourced_context" if exception else "measured",
                       "inputs": sources}
        contract_path = HERE / ("selected-" + suffix + "-measurement-contract.json")
        write(contract_path, {"format": "worker-measurement-contract",
                              "case_id": case_id, "requirements": [requirement],
                              "negative": {"remove": ["hydrant_survey.json"],
                                           "error_contains":
                                               "Missing required source: hydrant_survey.json"}})
        entry = {"case_id": case_id, "kind": "delivery", "id": "primary",
                 "construction": "native/" + construction_path.name,
                 "construction_sha256": sha(construction_path),
                 "candidate_risk": {"status": "physical", "reason":
                    "Original permission, hydrant, parking maneuver and pixels need Native review"},
                 "candidates": [],
                 "measurement_contract": "native/" + contract_path.name,
                 "measurement_procedure": {"entrypoint": "finalize.py",
                                           "status": "saved_source_diagnostic"},
                 "fixture_recipe": "work/" + ASSIGNMENT + "/native/selected-" +
                                   suffix + "-fixture-recipe.json"}
        entries.append(entry)
        comparison = next((item for item in plan["comparisons"]
                           if case_id in item["case_ids"]), None)
        proposals.append({"case_id": case_id, "target_law_id": "LVMC-11-52-130-A4",
                          "target_type": case["target_type"],
                          "rationale": "Source-bound hydrant geometry and permission contrast; legal outcome unresolved",
                          "paired_probe_id": comparison["comparison_id"] if comparison else None,
                          "deliberate_differences": comparison["deliberate_differences"] if comparison else [],
                          "probe": {"primary_variable": case["comparison_variable"],
                                    "comparison_or_standard": branch["branch"],
                                    "target_value_or_branch": config["requested_clearance_ft"]},
                          "variable_assignments": {case["comparison_variable"]: {
                              "kind": "controller", "value": config["requested_clearance_ft"],
                              "unit": "feet"}},
                          "unresolved_judgment_calls": plan["unresolved_judgment_calls"],
                          "recording_description": config["recording_description"]})
    write(ROOT / "proposals/cases.json", {"cell_id": "C200568",
          "actor": "motor_vehicle_driver", "status": "draft", "sweep_specs": [],
          "cases": proposals})
    manifest = ROOT / "selected-compat-manifest.json"
    write(manifest, {"format": "worker-execution-manifest",
                     "assignment_id": ASSIGNMENT,
                     "runtime_manifest_sha256": RUNTIME_SHA,
                     "status": "provisional_public_compatibility_only", "cases": entries})
    print(json.dumps({"manifest_sha256": sha(manifest), "cases": len(entries)}))


if __name__ == "__main__":
    main()
