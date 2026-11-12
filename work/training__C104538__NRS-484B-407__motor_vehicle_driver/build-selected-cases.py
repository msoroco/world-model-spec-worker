"""Select the authored 450/500/550-foot sweep for CPU preparation only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ("primary", "fallback1", "fallback2", "fallback3")
LAW = ("A vehicle shall not be turned so as to proceed in the opposite direction "
       "upon any curve, or upon the approach to or near the crest of a grade, "
       "where such vehicle cannot be seen by the driver of any other vehicle "
       "approaching from either direction within 500 feet.")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build() -> dict:
    assignment_path = ROOT / "inputs" / HERE.name / "assignment.json"
    assignment = read(assignment_path)
    plan = read(HERE / "case-plan.json")
    proposal = read(HERE / "proposals/cases.json")
    draft = read(HERE / "draft-execution-manifest.json")
    accepted = assignment["local_snapshot"]["memberships"]["full-train"]
    if (assignment["law_record"]["text"] != LAW or
            len(accepted) != 2 or
            any(row["status"] != "accepted" for row in accepted) or
            draft["assignment_id"] != HERE.name):
        raise ValueError("Frozen law or historical accepted membership changed")
    planned = {item["case_id"] for item in plan["cases"]}
    proposed = {item["case_id"] for item in proposal["cases"]}
    if (planned != proposed or
            planned != {item["case_id"] for item in draft["cases"]} or
            {case.rsplit("__", 1)[-1] for case in planned} !=
            {"below_500_ft", "at_500_ft", "above_500_ft"} or
            len(plan["comparisons"]) != 1 or
            plan["comparisons"][0]["case_ids"] !=
                [item["case_id"] for item in draft["cases"]]):
        raise ValueError("Reviewed three-case visibility sweep changed")
    manifest = {
        "format": "worker-execution-manifest",
        "assignment_id": HERE.name,
        "runtime_manifest_sha256": sha(ROOT / "runtime/pipeline/SOURCE-MANIFEST.json"),
        "status": "partial_selected_cpu_proofs_pending",
        "selection_review": {
            "law_input_sha256": sha(assignment_path),
            "case_plan_sha256": sha(HERE / "case-plan.json"),
            "proposal_sha256": sha(HERE / "proposals/cases.json"),
            "historical_accepted_recording_ids": [row["recording_id"] for row in accepted],
            "historical_reuse_receipt": None,
            "unresolved": [
                "accepted straight/U-turn equivalence lacks source-hashed review in export",
                "original 500-foot driver-eye, body and pixel visibility from both directions",
                "Native road/obstruction geometry, physical reversal and source-camera pixels",
            ],
            "scope": "Select distinct authored sweep cases for CPU preparation; no replay or physical/legal acceptance",
        },
        "cases": [],
    }
    for draft_entry in draft["cases"]:
        case = draft_entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        selected = {key: draft_entry[key] for key in
                    ("case_id", "candidate_risk", "measurement_contract",
                     "measurement_procedure")}
        recipe = (f"work/{HERE.name}/update015-{suffix}-primary-recipe.json")
        if not (ROOT / recipe).is_file():
            raise ValueError("Current primary fixture recipe missing: " + case)
        selected["fixture_recipe"] = recipe
        selected.update(kind="delivery", candidates=[],
                        native_handoff={"python_env_var": "CARLA_PYTHON",
                                        "host_env_var": "CARLA_HOST",
                                        "port_env_var": "CARLA_PORT"},
                        preparation_status="selected; original visibility and equivalence unverified")
        for ident in NAMES:
            source = (draft_entry if ident == "primary" else
                      next(item for item in draft_entry["candidates"]
                           if item["id"] == ident))
            source_path = HERE / source["construction"]
            if sha(source_path) != source["construction_sha256"]:
                raise ValueError("Draft construction changed: " + case + " " + ident)
            construction = read(source_path)
            if construction["case_id"] != case:
                raise ValueError("Construction selects another case")
            config_file = next(item for item in construction["files"]
                               if item["path"] == "config.json")
            config = json.loads(config_file["content"])
            if config["selected_case_id"] != case or config["candidate_id"] != ident:
                raise ValueError("Config selects another case or candidate")
            config["status"] = "selected_cpu_construction_original_visibility_unverified"
            config_file["content"] = json.dumps(config, indent=2) + "\n"
            construction["status"] = "selected_cpu_construction_original_visibility_unverified"
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
                row.update(trigger=source["trigger"], changed_knobs=source["changed_knobs"])
                selected["candidates"].append(row)
        manifest["cases"].append(selected)
    write(HERE / "execution-manifest.json", manifest)
    return {"selected_cases": len(manifest["cases"]),
            "candidate_constructions": sum(1 + len(c["candidates"])
                                           for c in manifest["cases"]),
            "status": manifest["status"]}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
