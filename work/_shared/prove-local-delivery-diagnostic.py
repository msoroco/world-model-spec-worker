"""Run pinned local-delivery CPU paths with an owned saved-source diagnostic.

This is synthetic integration evidence only. It does not claim Native capture,
full-train recording acceptance, or the canonical delivery gate proof.
"""
import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "runtime/pipeline"
SAVED = ROOT / "work/training__C382355__NRS-484B-400-1__motor_vehicle_driver/saved-fixture-proof.log"
ENV = dict(os.environ)
ENV["PYTHONPATH"] = os.pathsep.join((str(RUNTIME), str(RUNTIME / "scenario_pipeline"),
                                     str(RUNTIME / "python"), ENV.get("PYTHONPATH", "")))


def run(name, command):
    result = subprocess.run(command, cwd=ROOT, env=ENV, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=300)
    if result.returncode:
        raise RuntimeError(name + " failed:\n" + result.stdout[-2500:])
    skipped = "skipped=1" in result.stdout
    return {"scenario": name, "exit_code": result.returncode,
            "executed": not skipped,
            "output_tail": result.stdout.strip().splitlines()[-1]}


def main():
    prefix = "tests.test_worker_delivery_handoff.DeliveryHandoffTests."
    # These tests invoke the pinned local delivery functions against isolated
    # temporary stores, including a rejected audit before a positive accept.
    checks = [
        ("portable_exact_fallback_materialization", "tests.test_worker_candidates.CandidateTests.test_selects_exact_fallback_and_records_identity"),
        ("portable_tampered_candidate_rejection", "tests.test_worker_candidates.CandidateTests.test_rejects_unknown_and_tampered_candidate"),
        ("primary_and_fallback_job_preparation", prefix + "test_local_model_free_semantic_adoption"),
        ("exact_one_job_dispatch", prefix + "test_exact_dispatch_cannot_run_other_jobs"),
        ("rejected_audit_then_testing_acceptance", prefix + "test_local_acceptance_references_one_recording_in_both_sets"),
        ("selected_saved_processing_negative", "tests.test_worker_candidates.CandidateTests.test_saved_processing_rejects_mismatched_selection_before_conversion"),
    ]
    results = [run(name, [sys.executable, "-m", "unittest", target]) for name, target in checks]
    # The archived saved proof is source-bound. The current worker host has no
    # ffmpeg executable, so report its archival status rather than a rerun.
    report = json.loads(SAVED.read_text())
    rows = report["results"]
    if len(rows) != 2 or any(row["positive_exit_code"] != 0 or
                             row["negative_exit_code"] == 0 or
                             row["rebuild_required"] is not True or
                             row["source_unchanged"] is not True for row in rows):
        raise AssertionError("saved-source positive/negative contract changed")
    results.append({"scenario": "saved_source_positive_and_missing_source_negative",
                    "case_ids": [row["case_id"] for row in rows],
                    "frames_per_case": 4, "native_executed": False,
                    "archived_log": str(SAVED.relative_to(ROOT)),
                    "archived_log_sha256": hashlib.sha256(SAVED.read_bytes()).hexdigest(),
                    "rerun_on_current_host": False})
    print(json.dumps({"format": "worker-local-delivery-diagnostic-v1", "passed": False,
                      "synthetic_only": True, "canonical_gate_proof": False,
                      "reason": "Pinned local campaign integration tests skip on this portable worker checkout; live saved-source rerun needs ffmpeg, which is absent on this host",
                      "scenarios": results}, indent=2))


if __name__ == "__main__":
    main()
