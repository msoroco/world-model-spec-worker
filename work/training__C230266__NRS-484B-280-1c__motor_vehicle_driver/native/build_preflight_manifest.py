"""Prepare an incomplete exact-case manifest for public compatibility work."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    index = json.loads((ROOT / "selected-contract-index.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    by_id = {case["case_id"]: case for case in plan["cases"]}
    proposal_cases, entries = [], []
    for row in index["cases"]:
        cid = row["case_id"]
        suffix = cid.rsplit("__", 1)[-1]
        construction = json.loads((ROOT / row["construction"]).read_text())
        config = json.loads(next(file["content"] for file in construction["files"]
                                 if file["path"] == "config.json"))
        candidate = by_id[cid]
        proposal_cases.append({"case_id": cid, "target_law_id": plan["law_id"],
            "target_type": candidate["target_type"],
            "rationale": candidate["physical_target"] + "; outcome and legal judgment unverified",
            "variable_assignments": {"post_observation_ego_speed_request": {
                "kind": "controller", "value": config["mode"]}},
            "unresolved_judgment_calls": ["actual driver observation",
                "whether pedestrian is in the sourced statutory position",
                "proper caution after observation"],
            "recording_description": construction["recording_description"]})
        recipe = ROOT / ("selected-recipe-" + suffix + ".json")
        entries.append({"case_id": cid, "kind": "delivery",
            "construction": row["construction"],
            "construction_sha256": row["construction_sha256"],
            "measurement_contract": row["measurement_contract"],
            "measurement_procedure": {"entrypoint": "finalize.py",
                                      "output_schema": "worker-nrs280-caution-analysis-v1"},
            "fixture_recipe": str(recipe.relative_to(REPO)) if recipe.is_file() else None,
            "candidate_risk": {"status": "physical",
                               "reason": "Pedestrian and context camera visibility require original measurement"},
            "candidates": [], "delivery_readiness": "incomplete"})
    proposal = {"cell_id": plan["cell_id"], "actor": plan["actor"],
                "status": "draft", "cases": proposal_cases,
                "sweep_specs": [], "sweeps_expanded": True}
    dump(ROOT / "proposals" / "cases.json", proposal)
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": sha(REPO / "runtime" / "SOURCE-MANIFEST.json"),
                "status": "selected_cpu_preparation_incomplete", "cases": entries}
    dump(ROOT / "selected-preflight-manifest.json", manifest)
    print(json.dumps({"cases": len(entries),
                      "preflight_manifest_sha256": sha(ROOT / "selected-preflight-manifest.json")}))


if __name__ == "__main__":
    build()
