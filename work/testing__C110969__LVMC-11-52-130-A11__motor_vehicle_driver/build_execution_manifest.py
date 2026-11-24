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
        log_name = "cpu-native-finalize-offline-" + suffix + ".log"
        log = HERE / log_name
        if not log.is_file() or '"offline_passed": true' not in log.read_text():
            raise ValueError("Exact current-runtime offline proof missing: " + case_id)
        entries.append({
            "case_id": case_id, "kind": "delivery",
            "status": "partial_cpu_preparation",
            "construction": selected["construction"],
            "construction_sha256": selected["construction_sha256"],
            "candidate_risk": by_case[case_id]["candidate_risk"],
            "candidates": [],
            "offline": {
                "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + HERE.name +
                           "/execution-manifest.draft.json --case " + case_id +
                           " --output .runtime-work/c110969-finalize-offline-v2/" + suffix +
                           " --python $PWD/.venv-cpu/bin/python",
                "exit_code": 0, "log": log_name, "log_sha256": sha(log),
                "construction_sha256": selected["construction_sha256"]},
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST",
                               "port_env_var": "CARLA_PORT"},
            "pending_cpu_proofs": [
                "reviewed Native map and original context source packet binding",
                "physical three-outcome and lifecycle proofs",
                "canonical exact-case finalizer and measurement contract",
                "positive and negative compatibility",
                "saved-only processing",
                "independent delivery and comparison acceptance",
                "risk-justified fallback construction and offline/compatibility proof"],
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
