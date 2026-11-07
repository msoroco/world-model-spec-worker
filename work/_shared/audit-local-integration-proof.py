"""Independently exercise the pinned queue proof gate on a synthetic mini repo."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.delivery_handoff import validate_queue


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def rejected(repo, expected):
    try:
        validate_queue(repo, ["synthetic_assignment"])
    except ValueError as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("Pinned proof gate accepted a negative")


def main():
    proof = json.loads((HERE / "local-integration-proof.json").read_text())
    log = HERE / "local-delivery-diagnostic.log"
    digest = hashlib.sha256(log.read_bytes()).hexdigest()
    assert proof["log_sha256"] == digest
    assert proof["synthetic_only"] is True and proof["physical_validation_mocked"] is True
    assert proof["original_native_executed"] is False
    case = "synthetic_assignment__case"
    with tempfile.TemporaryDirectory(prefix="local-proof-gate-") as temporary:
        repo = Path(temporary)
        write(repo / "batch.json", {"canonical_delivery_queue_required": True,
                                    "target_set": "full-train"})
        write(repo / "work/synthetic_assignment/execution-manifest.json",
              {"cases": [{"case_id": case, "candidates": [{"id": "primary"},
                                                            {"id": "fallback1"}]}]})
        write(repo / "work/synthetic_assignment/case-plan.json", {"comparisons": []})
        row = {"order": 1, "assignment_id": "synthetic_assignment", "case_id": case}
        for key in ("capture_command", "postprocessing_command",
                    "owner_release_command", "additional_source_audit_command"):
            row[key] = "check " + case
        for key, action in (("prepare_command", "prepare-delivery"),
                            ("execute_command", "execute-delivery"),
                            ("accept_command", "accept-delivery")):
            row[key] = action + " " + case
        row["candidate_commands"] = {candidate: "prepare-delivery " + case + " " + candidate
                                     for candidate in ("primary", "fallback1")}
        write(repo / "work/_shared/gpu-queue.json",
              {"format": "worker-ordered-gpu-queue-v1", "cases": [row],
               "comparison_audit_commands": []})
        target = repo / "work/_shared/local-integration-proof.json"
        write(target, proof)
        shutil.copy2(log, repo / proof["log"])
        assert validate_queue(repo, ["synthetic_assignment"])["cases"] == 1
        copied = repo / proof["log"]
        copied.write_bytes(copied.read_bytes() + b"tampered\n")
        rejected(repo, "Missing tested canonical delivery integration proof")
        shutil.copy2(log, copied)
        mutated = dict(proof)
        mutated["scenarios"] = [s for s in proof["scenarios"] if s != "fallback_job"]
        write(target, mutated)
        rejected(repo, "Missing tested canonical delivery integration proof")
    receipt = {"format": "worker-local-integration-gate-audit-v1",
               "passed": True, "synthetic_only": True,
               "pinned_positive": 1, "tampered_log_negative": 1,
               "missing_fallback_negative": 1,
               "proof_sha256": hashlib.sha256((HERE / "local-integration-proof.json").read_bytes()).hexdigest(),
               "log_sha256": digest}
    write(HERE / "local-integration-gate-audit.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
