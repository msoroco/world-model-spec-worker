"""Bind source-derived CPU physical outcomes and tested lifecycle ordering."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    life_log = HERE / "physical-lifecycle.log"
    lifecycle = json.loads(life_log.read_text())
    assert lifecycle["events"] == EVENTS and lifecycle["closure_verified"] and lifecycle["negative_pre_exit_rejected"]
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.split("__")[-1]
        group = "sweep-cases" if "pending-" in suffix else "cases"
        prefix = f"{group}/{suffix}/"
        fixtures = []
        for kind in KINDS:
            result = prefix + f"physical-{kind}.json"
            log = prefix + f"physical-{kind}.log"
            proof = json.loads((HERE / result).read_text())
            recorded = json.loads((HERE / log).read_text())
            assert proof["case_id"] == recorded["case_id"] == case
            assert proof["physical_checks"]["maneuver"]["status"] == recorded["status"]
            assert proof["provenance_kind"] == "synthetic_fixture" and proof["diagnostic_fixture"] is True
            fixtures.append({
                "kind": kind,
                "command": "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c144550-physical-outcomes PYTHONPATH=runtime:runtime/scenario_pipeline .venv-cpu/bin/python work/" + HERE.name + "/prove_selected_physical_outcome.py --case " + case + " --kind " + kind,
                "exit_code": 0,
                "log": log,
                "log_sha256": sha(HERE / log),
                "result": result,
                "result_sha256": sha(HERE / result),
            })
        receipt = {"format": "worker-physical-preparation", "case_id": case,
                   "construction_sha256": entry["construction_sha256"],
                   "fixtures": fixtures,
                   "lifecycle": {"events": EVENTS, "exit_code": 0,
                                 "command": "SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c144550-physical-outcomes PYTHONPATH=runtime:runtime/scenario_pipeline .venv-cpu/bin/python work/" + HERE.name + "/prove_physical_lifecycle.py",
                                 "log": "physical-lifecycle.log", "log_sha256": sha(life_log)},
                   "scope": "synthetic CPU physical and lifecycle checker; no Native or legal acceptance"}
        receipt_path = HERE / group / suffix / "physical-preparation.json"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        entry["physical_preparation"] = {"receipt": prefix + "physical-preparation.json",
                                         "sha256": sha(receipt_path)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"selected_physical_proofs_bound": len(manifest["cases"])}))


if __name__ == "__main__":
    main()
