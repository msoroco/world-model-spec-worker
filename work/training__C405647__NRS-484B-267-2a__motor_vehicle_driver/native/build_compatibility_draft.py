"""Bind two exact selected CPU drafts to current-runtime compatibility inputs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def build():
    draft = json.loads((HERE / "selected-draft-manifest.json").read_text())
    cases = []
    for entry in draft["cases"]:
        suffix = entry["case_id"][-1]
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = next(json.loads(item["content"]) for item in construction["files"]
                      if item["path"] == "config.json")
        cases.append({"case_id": entry["case_id"], "target_law_id": "NRS-484B-267-2a",
                      "target_type": "judgment_sweep", "rationale": "Exact selected moving emergency-vehicle speed diagnostic",
                      "variable_assignments": {
                          "ego_target_speed_mps": {"kind": "controller", "value": config["ego_target_speed_mps"],
                                                   "unit": "m/s"},
                          "emergency_actor_moving": {"kind": "world_setup", "value": True,
                                                     "unit": "boolean"},
                          "officer_direction": {"kind": "world_setup", "value": False,
                                                "unit": "boolean"}},
                      "unresolved_judgment_calls": [
                          "original vehicle authorization and lamp qualification",
                          "reasonable and proper speed under NRS 484B.600(1)"],
                      "recording_description": construction["recording_description"],
                      "sweep_measurements": []})
    proposal = {"cell_id": "C405647", "actor": "motor_vehicle_driver", "status": "draft",
                "sweeps_expanded": True, "sweep_specs": [], "cases": cases}
    write(FOLDER / "proposals/cases.json", proposal)
    entries = []
    for entry in draft["cases"]:
        suffix = entry["case_id"][-1]
        entries.append({"case_id": entry["case_id"], "kind": "compatibility_draft",
                        "id": "primary", "construction": "native/" + entry["construction"],
                        "construction_sha256": entry["construction_sha256"],
                        "measurement_procedure": entry["measurement_procedure"],
                        "measurement_contract": "native/" + entry["measurement_contract"],
                        "fixture_recipe": "work/" + FOLDER.name + "/compatibility-recipe-" + suffix + ".json",
                        "candidate_risk": entry["candidate_risk"], "candidates": []})
    manifest = {"format": "worker-execution-manifest", "assignment_id": FOLDER.name,
                "status": "compatibility_draft_not_delivery_ready", "delivery_ready": False,
                "original_native_observed": False,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "cases": entries}
    write(FOLDER / "compatibility-draft-manifest.json", manifest)
    return {"manifest_sha256": sha(FOLDER / "compatibility-draft-manifest.json"),
            "proposal_sha256": sha(FOLDER / "proposals/cases.json")}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
