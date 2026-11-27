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
        compatibility = HERE / ("cpu-compat-" + ("steady" if kind == "steady_travel" else "variation") + ".json")
        positive_log = HERE / ("cpu-compat-" + ("steady" if kind == "steady_travel" else "variation") + "-analysis.log")
        negative_log = HERE / ("cpu-compat-" + ("steady" if kind == "steady_travel" else "variation") + "-negative.log")
        physical = HERE / ("physical-preparation-" + kind + ".json")
        acceptance = HERE / ("delivery-acceptance-" + kind + ".json")
        channels = content["recording_description"]["channels"]
        acceptance_binding = json.loads(acceptance.read_text())
        acceptance_binding["production_source_audit"] = {
            "script": "production_audit.py",
            "script_sha256": digest(HERE / "production_audit.py"),
            "command": ".venv-cpu/bin/python work/" + AID +
                       "/production_audit.py --case " + case +
                       " --attempt $ATTEMPT --output $SOURCE_AUDIT_RECEIPT",
            "physical_completion": "pending_independent_review",
            "legal_judgment": "unresolved"}
        cases.append({"case_id": case, "kind": "delivery",
                      "construction": entry["construction"],
                      "construction_sha256": digest(construction),
                      "measurement_contract": "measurement-contract-" + kind + ".json",
                      "measurement_procedure": {"entrypoint": "saved_finalizer.py"},
                      "fixture_recipe": "work/" + AID + "/fixture-recipe-" + kind + ".json",
                      "compatibility": {"receipt": compatibility.name, "sha256": digest(compatibility),
                                        "log": positive_log.name},
                      "negative": {"log": negative_log.name},
                      "physical_preparation": {"receipt": physical.name, "sha256": digest(physical)},
                      "delivery_acceptance": acceptance_binding,
                      "acquisition": {channel["name"]: {"entrypoint": "runtime_publication.py",
                          "method": "publish_original", "evidence": "operation.jsonl and original Native context"}
                          for channel in channels},
                      "native_handoff": {"python_env_var": "CARLA_PYTHON", "host_env_var": "CARLA_HOST",
                                         "port_env_var": "CARLA_PORT"},
                      "candidate_risk": {"status": "none",
                          "reason": "No case-specific Native failure has been measured; same reviewed alley route and controller variation preserve the comparison."},
                      "candidates": [],
                      "offline": {"construction_sha256": digest(construction),
                          "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + AID +
                              "/execution-manifest.draft.json --case " + case +
                              " --output .runtime-work/c10301-nov27-offline-v3-" + kind,
                          "exit_code": 0,
                          "log": "cpu-nov27-interior-offline-" + kind + ".log",
                          "log_sha256": digest(HERE / ("cpu-nov27-interior-offline-" + kind + ".log"))},
                      "remaining_original_reviews": [
                          "source-backed interior-attention sweep feasibility and realization",
                          "reviewed original site and municipal source binding",
                          "original Native physical completion review"]})
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": batch["runtime"]["source_manifest_sha256"],
                "semantic_index_sha256": digest(HERE / "proposals/semantic-index.json"),
                "cases": cases,
                "comparison_audit": {
                    "comparison_id": "alley_lateral_control_observation",
                    "script": "production_audit.py",
                    "script_sha256": digest(HERE / "production_audit.py"),
                    "command": ".venv-cpu/bin/python work/" + AID +
                               "/production_audit.py --steady $STEADY_ATTEMPT"
                               " --variation $VARIATION_ATTEMPT --output $COMPARISON_AUDIT_RECEIPT",
                    "physical_completion": "pending_independent_review",
                    "legal_judgment": "unresolved"}}
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("selected two exact alley cases; partial proofs remain")


if __name__ == "__main__":
    build()
