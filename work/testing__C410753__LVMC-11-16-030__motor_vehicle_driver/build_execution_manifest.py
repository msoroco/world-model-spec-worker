"""Bind each selected railway construction to its exact portable CPU bundle."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    if plan.get("assignment_id") != HERE.name:
        raise ValueError("railway execution plan assignment differs")
    entries = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        key = case_id.removeprefix(HERE.name + "__")
        if case_id != HERE.name + "__" + key or not key.isidentifier():
            raise ValueError("railway selected case identity differs")
        rel = "cases/" + key + "/construction.json"
        path = HERE / rel
        construction = json.loads(path.read_text())
        if construction.get("case_id") != case_id:
            raise ValueError("railway exact construction differs")
        entries.append({
            "case_id": case_id, "construction": rel,
            "construction_sha256": sha(path),
            "measurement_contract": "cases/" + key + "/measurement-contract.json",
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "fixture_recipe": "work/" + HERE.name + "/diagnostic-fixtures/" + key + "/fixture-recipe.json",
            "candidate_risk": case["candidate_risk"],
        })
    batch = json.loads((REPO / "batch.json").read_text())
    manifest = {"assignment_id": HERE.name, "cases": entries,
                "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
                "status": "partial", "physical_completion_confirmed": False}
    (HERE / "execution-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return len(entries)


if __name__ == "__main__":
    print(build())
