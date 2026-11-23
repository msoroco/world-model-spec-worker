"""Bind exact case constructions and CPU recipes for pinned compatibility runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    draft = json.loads((ROOT / "execution-manifest.draft.json").read_text())
    cases = []
    for item in draft["cases"]:
        suffix = item["case_id"].rsplit("__", 1)[-1]
        construction = ROOT / item["construction"]
        contract = ROOT / item["measurement_contract"]
        recipe = ROOT / "diagnostics" / suffix / "fixture-recipe.json"
        if sha(construction) != item["construction_sha256"]:
            raise ValueError("stale exact construction: " + suffix)
        if not contract.is_file() or not recipe.is_file():
            raise ValueError("missing exact contract or recipe: " + suffix)
        cases.append({
            "case_id": item["case_id"], "kind": "delivery",
            "construction": item["construction"],
            "construction_sha256": item["construction_sha256"],
            "measurement_contract": item["measurement_contract"],
            "measurement_procedure": item["measurement_procedure"],
            "fixture_recipe": str(recipe.relative_to(REPO)),
            "candidate_risk": item["candidate_risk"],
            "candidates": [],
            "proof_status": "diagnostic_compatibility_pending",
        })
    manifest = {
        "format": "worker-execution-manifest",
        "assignment_id": draft["assignment_id"],
        "runtime_manifest_sha256": sha(REPO / "runtime" / "SOURCE-MANIFEST.json"),
        "cases": cases,
        "status": "partial_cpu_compatibility_under_construction",
    }
    (ROOT / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print("bound", len(build()["cases"]), "exact diagnostic compatibility cases")
