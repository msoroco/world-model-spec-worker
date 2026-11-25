"""Build an isolated provisional selected manifest for electric CPU compatibility.

The stage lives under .runtime-work. It is not an accepted asset/source claim.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
STAGE = REPO / ".runtime-work/c104538-electric-selection-stage"
PACKAGE = STAGE / "work" / ROOT.name
MACHINES = ("electric_bicycle", "electric_scooter")
BEHAVIORS = (("obey", "controlled_1", "mounted-obey"),
             ("turn", "controlled_2", "mounted-turn"),
             ("dismount", "controlled_3", "dismounted-turn"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    PACKAGE.mkdir(parents=True)
    plan = json.loads((ROOT / "case-plan.json").read_text())
    proposals = json.loads((ROOT / "proposals/cases.json").read_text())
    base_labels = {"controlled_1", "controlled_2", "controlled_3"}
    plan["cases"] = [item for item in plan["cases"]
                     if item["case_id"].split("__")[-1] in base_labels]
    plan["comparisons"] = [item for item in plan["comparisons"]
                           if "electric_bicycle_comparison" not in item["comparison_id"]
                           and "electric_scooter_comparison" not in item["comparison_id"]]
    proposals["cases"] = [item for item in proposals["cases"]
                          if item["target_type"] == "baseline"
                          or item["case_id"].split("__")[-1] in base_labels]
    manifest = {"format": "worker-execution-manifest", "assignment_id": ROOT.name,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "cases": []}
    original_proposals = {item["case_id"].split("__")[-1]: item
                          for item in proposals["cases"]}
    for machine in MACHINES:
        class_cases = []
        for behavior, base_case, base_recipe in BEHAVIORS:
            label = f"{machine}_{behavior}"
            case_id = f"{ROOT.name}__{label}"
            class_cases.append(case_id)
            draft = ROOT / "electric-drafts" / label / "construction.json"
            staged_draft = PACKAGE / "electric-drafts" / label / "construction.json"
            staged_draft.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(draft, staged_draft)
            staged_fallback = staged_draft.parent / "fallback1/construction.json"
            staged_fallback.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(draft.parent / "fallback1/construction.json", staged_fallback)
            base_proposal = original_proposals[base_case]
            selected_proposal = json.loads(json.dumps(base_proposal))
            selected_proposal["case_id"] = case_id
            selected_proposal["recording_description"] = json.loads(draft.read_text())["recording_description"]
            selected_proposal["physical_target"] = selected_proposal["physical_target"].replace("bicycle", machine.replace("_", " "))
            proposals["cases"].append(selected_proposal)
            base_plan = next(item for item in plan["cases"] if item["case_id"].endswith("__" + base_case))
            selected_plan = json.loads(json.dumps(base_plan))
            selected_plan["case_id"] = case_id
            selected_plan["physical_target"] = selected_plan["physical_target"].replace("bicycle", machine.replace("_", " "))
            plan["cases"].append(selected_plan)
            base_contract = json.loads((ROOT / f"v2-{base_recipe}-measurement-contract.json").read_text())
            base_contract["case_id"] = case_id
            base_contract["requirements"][0]["disposition_index"] = 4 if machine == "electric_bicycle" else 5
            contract_path = PACKAGE / "electric-drafts" / label / "measurement-contract.json"
            save(contract_path, base_contract)
            recipe = json.loads((ROOT / f"v2-{base_recipe}-primary-recipe.json").read_text())
            for item in recipe["sources"]:
                source = REPO / item["source"]
                if item["path"] == "rider_native_samples.jsonl":
                    source = REPO / ".runtime-work/c104538-electric" / ("saved-" + label) / "rider_native_samples.jsonl"
                    item["source"] = f"work/{ROOT.name}/electric-drafts/{label}/rider_native_samples.jsonl"
                elif item["path"] == "rider-source-manifest.json":
                    source = REPO / ".runtime-work/c104538-electric" / ("saved-" + label) / "rider-source-manifest.json"
                    item["source"] = f"work/{ROOT.name}/electric-drafts/{label}/rider-source-manifest.json"
                dest = STAGE / item["source"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copyfile(source, dest)
                item["sha256"] = sha(dest)
            generator = recipe["generator"]
            generator_source = REPO / generator["source"]
            generator_dest = STAGE / generator["source"]
            generator_dest.parent.mkdir(parents=True, exist_ok=True)
            if not generator_dest.exists():
                shutil.copyfile(generator_source, generator_dest)
            generator["sha256"] = sha(generator_dest)
            recipe_path = PACKAGE / "electric-drafts" / label / "recipe.json"
            save(recipe_path, recipe)
            manifest["cases"].append({"case_id": case_id,
                                      "construction": str(staged_draft.relative_to(PACKAGE)),
                                      "construction_sha256": sha(staged_draft),
                                      "candidates": [{"id": "fallback1",
                                                      "construction": str(staged_fallback.relative_to(PACKAGE)),
                                                      "construction_sha256": sha(staged_fallback)}],
                                      "measurement_contract": str(contract_path.relative_to(PACKAGE)),
                                      "fixture_recipe": str(recipe_path.relative_to(STAGE)),
                                      "measurement_procedure": {"entrypoint": "finalize.py"}})
        disposition = plan["requirement_dispositions"][4 if machine == "electric_bicycle" else 5]
        disposition["status"] = "selected_required"
        disposition["case_ids"] = class_cases
        plan["comparisons"].append({"comparison_id": f"{ROOT.name}__{machine}_comparison",
                                    "case_ids": class_cases[:2],
                                    "fixed_conditions": ["C104538 U-turn cell, sign, camera and timebase"],
                                    "deliberate_differences": ["requested mounted U-turn"]})
    save(PACKAGE / "case-plan.json", plan)
    save(PACKAGE / "proposals/cases.json", proposals)
    save(PACKAGE / "execution-manifest.json", manifest)
    print(json.dumps({"stage_manifest": str(PACKAGE / "execution-manifest.json"),
                      "case_count": len(manifest["cases"])}, sort_keys=True))


if __name__ == "__main__":
    main()
