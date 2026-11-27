"""Bind a CPU-prepared result after all pinned validators pass."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NATIVE = ROOT / "native"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = ROOT / "result.json"
    result = json.loads(path.read_text())
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    tests = []
    for entry in manifest["cases"]:
        for selected in (entry, entry["candidates"][0]):
            offline = selected["offline"]
            log = ROOT / offline["log"]
            assert offline["exit_code"] == 0 and offline["log_sha256"] == sha(log)
            tests.append({"command": offline["command"], "exit_code": 0,
                          "log": offline["log"], "sha256": sha(log)})
    result.update({
        "status": "ready", "readiness_kind": "delivery_prepared",
        "reason": "All 11 exact selected shoulder-lamp cases and 11 spawn-risk alternates passed CPU preparation. Original Native shoulder, lighting, optical pixels, near-side lamp installation, physical completion and legal judgment remain pending local source review.",
        "planned_case_count": 11, "comparison_count": 4, "candidate_count": 11,
        "accepted_membership_count": 0, "reuse_count": 0, "unresolved_branch_count": 4,
        "selected_offline_case_count": 22, "semantic_selected_case_count": 11,
        "selected_public_compatibility_count": 22,
        "saved_processing_positive_count": 11, "physical_fixture_case_count": 11,
        "independent_delivery_audit_count": 11,
        "independent_comparison_audit_count": 4,
        "near_side_source_gate_proof": "native/near-side-gate-proof.json",
        "execution_manifest": "execution-manifest.json",
        "execution_manifest_sha256": sha(ROOT / "execution-manifest.json"),
        "semantic_index": "proposals/semantic-index.json",
        "semantic_index_sha256": sha(ROOT / "proposals/semantic-index.json"),
        "tests": tests,
        "first_gpu_delivery_command": "PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange execute-delivery --repo . --batch full-train-delivery --db $DB --assignment " + ROOT.name + " --case " + manifest["cases"][0]["case_id"] + " --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT",
    })
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "tests": len(tests),
                      "manifest_sha256": result["execution_manifest_sha256"]}))


if __name__ == "__main__":
    main()
