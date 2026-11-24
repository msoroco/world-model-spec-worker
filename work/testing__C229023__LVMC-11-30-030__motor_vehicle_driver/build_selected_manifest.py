"""Bind six exact crosswalk constructions and contracts to selected delivery.

The manifest remains partial until source-shaped compatibility, fallbacks,
saved processing, and independent acceptance proofs are supplied.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from case_construction import CASES
from crosswalk_measurements import ASSIGNMENT_ID

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(seal_offline: bool = False) -> dict:
    draft = json.loads((HERE / "execution-manifest.draft.json").read_text())
    expected = {ASSIGNMENT_ID + "__" + suffix for suffix in CASES}
    if draft.get("assignment_id") != ASSIGNMENT_ID or {row["case_id"] for row in draft["cases"]} != expected:
        raise ValueError("all six exact diagnostic constructions required")
    plan = json.loads((HERE / "case-plan.json").read_text())
    if {row["case_id"] for row in plan["cases"]} != expected:
        raise ValueError("selected case plan differs")
    fallback = json.loads((HERE / "fallback-draft.json").read_text()) if (HERE / "fallback-draft.json").is_file() else {"candidates": {}}
    rows = []
    for row in draft["cases"]:
        case_id = row["case_id"]
        suffix = case_id.removeprefix(ASSIGNMENT_ID + "__")
        construction = HERE / row["construction"]
        contract = HERE / "cases" / suffix / "measurement-contract.json"
        if not contract.is_file() or _sha(construction) != row["construction_sha256"]:
            raise ValueError("selected construction or measurement contract missing/changed")
        source = json.loads(construction.read_text())
        files = {item["path"] for item in source["files"]}
        if "analysis.py" not in files or "canonical_evidence.py" not in files or source["case_id"] != case_id:
            raise ValueError("selected saved analysis/source projection missing")
        offline = {"status": "pending selected-manifest proof"}
        if seal_offline:
            log_name = "cpu-selected-offline-" + suffix + ".log"
            log = HERE / log_name
            if not log.is_file():
                raise ValueError("selected offline proof missing: " + suffix)
            proof = json.loads(log.read_text())
            if (proof.get("case_id") != case_id or proof.get("candidate_id") != "primary" or
                    proof.get("offline_passed") is not True or proof.get("simulation_started") is not False):
                raise ValueError("exact selected offline proof failed: " + suffix)
            offline = {"command": ".venv-cpu/bin/python runtime.py offline --manifest "
                       + "work/" + ASSIGNMENT_ID + "/execution-manifest.json --case "
                       + case_id + " --output .runtime-work/lead-nov24-sixth/selected-" + suffix
                       + " --python $PWD/.venv-cpu/bin/python",
                       "exit_code": 0, "construction_sha256": row["construction_sha256"],
                       "log": log_name, "log_sha256": _sha(log)}
        candidates = [fallback["candidates"][case_id]] if case_id in fallback["candidates"] else []
        for candidate in candidates:
            if _sha(HERE / candidate["construction"]) != candidate["construction_sha256"]:
                raise ValueError("fallback construction changed")
        selected = {
            "case_id": case_id, "kind": "delivery",
            "construction": row["construction"],
            "construction_sha256": row["construction_sha256"],
            "measurement_contract": str(contract.relative_to(HERE)),
            "measurement_contract_sha256": _sha(contract),
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "candidate_risk": row["candidate_risk"],
            "candidates": candidates,
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
            "offline": offline,
            "missing_proofs": [
                "physical-risk fallback source-shaped compatibility and original motion review",
                "source-shaped positive/negative compatibility and selected measurement",
                "saved-only processing and independent delivery/comparison acceptance",
                "reviewed original road intersection, stopped-purpose and Native camera source packets",
            ],
        }
        rows.append(selected)
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT_ID,
                "runtime_manifest_sha256": _sha(REPO / "runtime" / "SOURCE-MANIFEST.json"),
                "status": "partial_selected_delivery", "cases": rows}
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal-offline", action="store_true")
    args = parser.parse_args()
    print("bound", len(build(args.seal_offline)["cases"]),
          "exact selected crosswalk entries; proofs remain partial")
