"""Bind the exact alley pair to current-runtime selected constructions, without claiming readiness."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    batch = json.loads((HERE.parents[1] / "batch.json").read_text())
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    selected = {row["case_id"]: row for row in proposal["cases"] if row["target_type"] != "baseline"}
    draft = json.loads((HERE / "execution-manifest.draft.json").read_text())
    if {entry["case_id"] for entry in draft["cases"]} != set(selected):
        raise ValueError("Exact alley constructions and semantic cases differ")
    cases = []
    for entry in draft["cases"]:
        case = entry["case_id"]
        kind = case.rsplit("__", 1)[1]
        construction = HERE / entry["construction"]
        content = json.loads(construction.read_text())
        if content["recording_description"] != selected[case]["recording_description"]:
            raise ValueError("Selected construction changes canonical recording plan")
        if digest(construction) != entry["construction_sha256"]:
            raise ValueError("Selected construction SHA mismatch")
        cases.append({"case_id": case, "kind": "delivery",
                      "construction": entry["construction"],
                      "construction_sha256": digest(construction),
                      "measurement_contract": "measurement-contract-" + kind + ".json",
                      "measurement_procedure": {"entrypoint": "saved_finalizer.py"},
                      "fixture_recipe": "work/" + AID + "/fixture-recipe-" + kind + ".json",
                      "candidate_risk": {"status": "none",
                          "reason": "No case-specific Native failure has been measured; same reviewed alley route and controller variation preserve the comparison."},
                      "candidates": [],
                      "offline": {"construction_sha256": digest(construction),
                          "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + AID +
                              "/execution-manifest.draft.json --case " + case +
                              " --output .runtime-work/c10301-010-nov24b/offline-" +
                              ("steady" if kind == "steady_travel" else "variation") + "-v11",
                          "exit_code": 0,
                          "log": "cpu-nov24b-offline-" + ("steady" if kind == "steady_travel" else "variation") + "-v11.log",
                          "log_sha256": digest(HERE / ("cpu-nov24b-offline-" + ("steady" if kind == "steady_travel" else "variation") + "-v11.log"))},
                      "missing_proofs": ["case-specific positive and negative runtime compatibility",
                                         "recorded-only process-saved proof on current analyzer revision",
                                         "independent delivery audit positive and negative",
                                         "source-bound comparison audit",
                                         "reviewed original site source binding"]})
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
                "semantic_index_sha256": digest(HERE / "proposals/semantic-index.json"),
                "status": "partial", "cases": cases}
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("selected two exact alley cases; partial proofs remain")


if __name__ == "__main__":
    build()
