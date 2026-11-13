"""Exercise the pinned exact-delivery queue validator for this selected pair.

The local integration receipt below is an explicitly temporary test double. This
proves queue shape and exact coverage, not full-batch integration or dispatch.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.delivery_handoff import validate_queue  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def main() -> None:
    fragment_path = HERE / "update026-selected-delivery-queue-fragment.json"
    fragment = json.loads(fragment_path.read_text())
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((HERE / "case-plan.json").read_text())
    assert fragment["execution_manifest_sha256"] == sha(manifest_path)
    assert not fragment["dispatchable"]
    assert [row["case_id"] for row in fragment["cases"]] == [
        item["case_id"] for item in manifest["cases"]]
    assert [row["comparison_id"] for row in fragment["comparison_audit_commands"]] == [
        item["comparison_id"] for item in plan["comparisons"]]
    assert all(not row["dispatchable"] for row in fragment["cases"])

    with tempfile.TemporaryDirectory(prefix="c10316-queue-contract-",
                                     dir=ROOT / ".runtime-work") as tmp:
        repo = Path(tmp)
        folder = repo / "work" / AID
        folder.mkdir(parents=True)
        shutil.copyfile(manifest_path, folder / "execution-manifest.json")
        shutil.copyfile(HERE / "case-plan.json", folder / "case-plan.json")
        write(repo / "batch.json", {"assignments": {AID: {"set_ids": ["full-train"]}}})
        log = repo / "mock-local-integration.log"
        log.write_text("QUEUE CONTRACT UNIT TEST ONLY; no local integration ran\n")
        write(repo / "work/_shared/local-integration-proof.json", {
            "format": "worker-local-integration-proof", "passed": True,
            "scenarios": ["primary_job", "fallback_job", "saved_processing",
                          "rejected_audit", "accepted_targets"],
            "exit_code": 0, "command": "mock-local-integration-for-unit-test",
            "log": log.name, "log_sha256": sha(log),
            "mock_local_integration_proof": True})
        queue = copy.deepcopy(fragment)
        queue["format"] = "worker-ordered-gpu-queue"
        queue_path = repo / "work/_shared/gpu-queue.json"
        write(queue_path, queue)
        positive = validate_queue(repo, {AID: {}})
        assert positive["cases"] == 2 and positive["comparisons"] == 1

        negatives = {}
        for label, mutate, expected in (
            ("missing_fallback", lambda q: q["cases"][0]["candidate_commands"].pop("fallback3"),
             "Queue does not cover exact fallback candidates"),
            ("missing_comparison", lambda q: q["comparison_audit_commands"].clear(),
             "Delivery queue omits a comparison audit"),
            ("wrong_case", lambda q: q["cases"][1].update(case_id="other-case"),
             "Delivery queue does not cover every exact case once"),
        ):
            changed = copy.deepcopy(queue)
            mutate(changed)
            write(queue_path, changed)
            try:
                validate_queue(repo, {AID: {}})
            except ValueError as exc:
                assert expected in str(exc), (label, str(exc))
                negatives[label] = str(exc)
            else:
                raise AssertionError("Queue mutation was accepted: " + label)

    proof = {
        "format": "c10316-queue-contract-cpu-proof-v1",
        "selected_manifest_sha256": sha(manifest_path),
        "fragment_sha256": sha(fragment_path),
        "runtime_validator_sha256": sha(ROOT / "runtime/pipeline/scenario_pipeline/worker_exchange/delivery_handoff.py"),
        "exact_cases": 2, "candidate_commands": 8, "comparison_commands": 1,
        "positive_validator_passed": True, "negative_rejections": negatives,
        "mock_local_integration_proof": True, "full_batch_integrated": False,
        "dispatchable": False, "original_native_or_pixel_acceptance": False,
    }
    target = HERE / "update028-queue-contract-proof.json"
    write(target, proof)
    print(json.dumps({"positive_validator_passed": True,
                      "negative_rejections": sorted(negatives),
                      "full_batch_integrated": False, "proof_sha256": sha(target)}))


if __name__ == "__main__":
    main()
