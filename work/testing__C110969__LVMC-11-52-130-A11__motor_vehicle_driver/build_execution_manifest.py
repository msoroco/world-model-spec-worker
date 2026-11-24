"""Select the seven proven offline constructions in a current-runtime manifest.

This file records only the CPU proofs that have passed. Pending fields are
explicit and cannot be mistaken for a delivery-ready result.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    draft = json.loads((HERE / "execution-manifest.draft.json").read_text())
    by_case = {case["case_id"]: case for case in plan["cases"]}
    entries = []
    for selected in draft["cases"]:
        case_id = selected["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        construction = HERE / selected["construction"]
        if sha(construction) != selected["construction_sha256"]:
            raise ValueError("Selected construction hash changed: " + case_id)
        log_name = "cpu-fallback-offline-primary-" + suffix + ".log"
        log = HERE / log_name
        if not log.is_file() or '"offline_passed": true' not in log.read_text():
            raise ValueError("Exact current-runtime offline proof missing: " + case_id)
        physical_path = HERE / "cases" / suffix / "physical-preparation.json"
        physical = json.loads(physical_path.read_text())
        if physical["case_id"] != case_id or physical["construction_sha256"] != selected["construction_sha256"]:
            raise ValueError("Exact physical fixture binding differs: " + case_id)
        fallback = dict(selected["candidates"][0])
        fallback_log_name = "cpu-fallback-offline-fallback1-" + suffix + ".log"
        fallback_log = HERE / fallback_log_name
        if not fallback_log.is_file() or '"offline_passed": true' not in fallback_log.read_text():
            raise ValueError("Exact fallback offline proof missing: " + case_id)
        fallback["offline"] = {
            "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + HERE.name +
                       "/execution-manifest.draft.json --case " + case_id +
                       " --candidate fallback1 --output .runtime-work/c110969-fallback-offline-v2/fallback1/" + suffix +
                       " --python $PWD/.venv-cpu/bin/python",
            "exit_code": 0, "log": fallback_log_name, "log_sha256": sha(fallback_log),
            "construction_sha256": fallback["construction_sha256"]}
        entries.append({
            "case_id": case_id, "kind": "delivery",
            "status": "partial_cpu_preparation",
            "construction": selected["construction"],
            "construction_sha256": selected["construction_sha256"],
            "candidate_risk": by_case[case_id]["candidate_risk"],
            "candidates": [fallback],
            "offline": {
                "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + HERE.name +
                           "/execution-manifest.draft.json --case " + case_id +
                           " --output .runtime-work/c110969-fallback-offline-v2/primary/" + suffix +
                           " --python $PWD/.venv-cpu/bin/python",
                "exit_code": 0, "log": log_name, "log_sha256": sha(log),
                "construction_sha256": selected["construction_sha256"]},
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST",
                               "port_env_var": "CARLA_PORT"},
            "physical_preparation": {"receipt": str(physical_path.relative_to(HERE)),
                                     "sha256": sha(physical_path)},
            "measurement_contract": "cases/" + suffix + "/measurement-contract.json",
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "pending_cpu_proofs": [
                "reviewed Native map and original context source packet binding",
                "positive and negative compatibility",
                "saved-only processing",
                "independent delivery and comparison acceptance",
                "fallback positive and negative compatibility proof"],
            "physical_preparation_status": "unverified_original_capture_pending",
            "legal_necessity": "unresolved"})
    if len(entries) != 7 or {e["case_id"] for e in entries} != set(by_case):
        raise ValueError("Seven selected exact cases required")
    output = {"format": "worker-execution-manifest",
              "assignment_id": HERE.name,
              "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
              "status": "partial_cpu_preparation",
              "semantic_index": "proposals/semantic-index.json",
              "cases": entries,
              "comparisons": plan["comparisons"]}
    (HERE / "execution-manifest.json").write_text(json.dumps(output, indent=2) + "\n")
    print("selected", len(entries), "cases against current runtime")


if __name__ == "__main__":
    main()
