"""Select the reviewed crosswalk pair for CPU proofs, without physical claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = "Pedestrians shall move whenever practicable upon the right half of crosswalks."
NAMES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build() -> dict:
    assignment_path = ROOT / "inputs" / HERE.name / "assignment.json"
    witness_path = ROOT / "inputs" / HERE.name / "witnesses.json"
    assignment, witnesses = read(assignment_path), read(witness_path)
    plan = read(HERE / "case-plan.json")
    proposal = read(HERE / "proposals/cases.json")
    draft = read(HERE / "draft-execution-manifest.json")
    if (assignment["law_record"]["text"] != LAW or
            len(witnesses) != 1 or witnesses[0]["witness"]["quote"] != LAW or
            witnesses[0]["witness"]["decision"] != "conditional" or
            assignment["local_snapshot"]["memberships"]["full-train"] or
            draft["assignment_id"] != HERE.name):
        raise ValueError("Crosswalk law, conditional witness or evidence changed")
    planned = {item["case_id"] for item in plan["cases"]}
    proposed = {item["case_id"] for item in proposal["cases"]
                if item["target_type"] != "baseline"}
    if (planned != proposed or
            planned != {item["case_id"] for item in draft["cases"]} or
            {case.rsplit("__", 1)[-1] for case in planned} !=
            {"reference", "contrast"} or len(plan["comparisons"]) != 1):
        raise ValueError("Reviewed controlled pair changed")
    manifest = {
        "format": "worker-execution-manifest",
        "assignment_id": HERE.name,
        "runtime_manifest_sha256": sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json"),
        "status": "partial_selected_cpu_proofs_pending",
        "selection_review": {
            "law_input_sha256": sha(assignment_path),
            "conditional_witness_sha256": sha(witness_path),
            "case_plan_sha256": sha(HERE / "case-plan.json"),
            "proposal_sha256": sha(HERE / "proposals/cases.json"),
            "accepted_full_train_memberships": 0,
            "unresolved": [
                "Native crosswalk designation and marked highway connection",
                "passage-space, obstacle, other-pedestrian and signal facts",
                "physical practicability and source-camera pixels",
            ],
            "scope": "Select exact cases for CPU preparation; no physical or legal acceptance",
        },
        "cases": [],
    }
    for draft_entry in draft["cases"]:
        case_id = draft_entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        selected = {key: draft_entry[key] for key in
                    ("case_id", "candidate_risk", "measurement_contract",
                     "measurement_procedure", "fixture_recipe")}
        selected.update(kind="delivery", candidates=[],
                        native_handoff={"python_env_var": "CARLA_PYTHON",
                                        "host_env_var": "CARLA_HOST",
                                        "port_env_var": "CARLA_PORT"},
                        preparation_status="selected; physical facts unverified")
        for ident in NAMES:
            source = (draft_entry if ident == "primary" else
                      next(item for item in draft_entry["candidates"]
                           if item["id"] == ident))
            source_path = HERE / source["construction"]
            if sha(source_path) != source["construction_sha256"]:
                raise ValueError("Draft construction changed: " + case_id + " " + ident)
            construction = read(source_path)
            if construction["case_id"] != case_id:
                raise ValueError("Construction selects another case")
            config_file = next(item for item in construction["files"]
                               if item["path"] == "config.json")
            config = json.loads(config_file["content"])
            if config["selected_case_id"] != case_id:
                raise ValueError("Config selects another case")
            config["status"] = "selected_cpu_construction_physical_unverified"
            config_file["content"] = json.dumps(config, indent=2) + "\n"
            construction["status"] = "selected_cpu_construction_physical_unverified"
            construction["measurement_plan"]["status"] = "cpu_software_compatible_physical_unverified"
            construction["selection_source"] = {
                "draft_construction": source["construction"],
                "draft_construction_sha256": source["construction_sha256"],
                "case_plan_sha256": manifest["selection_review"]["case_plan_sha256"],
            }
            relative = f"selected-candidates/{suffix}/{ident}/construction.json"
            path = HERE / relative
            write(path, construction)
            row = {"id": ident, "construction": relative,
                   "construction_sha256": sha(path)}
            if ident == "primary":
                selected.update(construction=relative,
                                construction_sha256=row["construction_sha256"])
            else:
                row.update(trigger=source["trigger"],
                           changed_knobs=source["changed_knobs"])
                selected["candidates"].append(row)
        manifest["cases"].append(selected)
    write(HERE / "execution-manifest.json", manifest)
    return {"selected_cases": len(manifest["cases"]),
            "candidate_constructions": sum(1 + len(c["candidates"])
                                           for c in manifest["cases"]),
            "status": manifest["status"]}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
