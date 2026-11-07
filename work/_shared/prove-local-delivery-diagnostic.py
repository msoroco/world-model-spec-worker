"""Run pinned local-delivery CPU paths with an owned saved-source diagnostic.

This is synthetic integration evidence only. It does not claim Native capture,
full-train recording acceptance, or the canonical delivery gate proof.
"""
import json
import hashlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


def run_campaign():
    # The pinned tests use a skip guard for runtime/pipeline/pipeline.py, while
    # this checkout supplies scenario_pipeline/pipeline.py. Invoke the original
    # methods with that package on sys.path; add the scope fixture omitted by
    # the pinned acceptance test. No frozen source is changed.
    sys.path[:0] = [str(RUNTIME), str(RUNTIME / "scenario_pipeline"),
                    str(RUNTIME / "python")]
    from tests.test_worker_delivery_handoff import DeliveryHandoffTests
    from worker_exchange.common import write
    from batch_pipeline import runtime_dependencies

    names = ("test_local_model_free_semantic_adoption",
             "test_exact_dispatch_cannot_run_other_jobs")
    suite = unittest.TestSuite()
    for name in names:
        original = getattr(DeliveryHandoffTests, name).__wrapped__
        setattr(DeliveryHandoffTests, name, original)
        suite.addTest(DeliveryHandoffTests(name))

    class ScopedAcceptance(DeliveryHandoffTests):
        def setUp(self):
            super().setUp()
            root = self.repo / "artifacts"
            for sid in ("demo-test", "full-test"):
                write(root / "sets" / sid / "scope.json", {"assignments": [
                    {"law_id": "LAW-1", "cell_id": "C1", "actor": "motor_vehicle_driver"}]})

        def test_training_target_acceptance(self):
            from worker_exchange.common import read, sha
            from worker_exchange.local_delivery import accept

            self.assignment["role"] = "training"
            root = self.repo / "artifacts"
            (root / "state").mkdir(parents=True, exist_ok=True)
            db = root / "state/delivery.sqlite"
            db.touch()
            case = self.case_ids[0]
            write(self.repo / "batch.json", {"assignments": {self.aid: {}}})
            write(self.repo / "inputs" / self.aid / "assignment.json", self.assignment)
            write(root / "sets/full-train/scope.json", {"assignments": [
                {"law_id": "LAW-1", "cell_id": "C1", "actor": "motor_vehicle_driver"}]})
            write(root / "sets/full-train/selection.json",
                  {"frozen": True, "members": [], "selection_version": "before"})
            rid = "b" * 64
            attempt = root / "recordings" / rid / "evidence"
            attempt.mkdir(parents=True)
            write(attempt.parent / "metadata.json", {"recording_id": rid, "campaign": "run",
                  "job_id": 7, "attempt": 1, "cell_id": "C1", "actor": "motor_vehicle_driver",
                  "case_id": case, "status": "recording", "phases": {}})
            write(attempt / "result.json", {"completion": {"binding": {}}})
            write(attempt / "trace.json", {"scenes": [{"t": 50}]})
            (attempt / "video.webm").write_bytes(b"synthetic-fixture-video")
            (attempt / "video_frames.jsonl").write_text(json.dumps(
                {"video_frame": 0, "time_s": 0.05}) + "\n")
            audit = {"format": "worker-delivery-audit-v1", "passed": True,
                     "case_id": case, "job_id": 7, "attempt": 1,
                     "recording_id": rid, "frames": 1,
                     "source_result_sha256": sha(attempt / "result.json"),
                     "video": "video.webm", "video_sha256": sha(attempt / "video.webm"),
                     "trace": "trace.json", "trace_sha256": sha(attempt / "trace.json"),
                     "checks": {key: True for key in (
                         "native_source", "all_participants", "time_join",
                         "full_video_decode", "actual_pixels", "physical_completion")}}
            write(attempt / "audit.json", audit)
            job = {"id": 7, "stage": "execution", "status": "completed", "attempts": 1,
                   "actor": "motor_vehicle_driver", "artifact_id": "artifact",
                   "payload": json.dumps({"cell": {"cell_id": "C1"}, "case": {
                       "case_id": case, "target_law_id": "LAW-1"}})}

            class FakeDB:
                def execute(self, *_args): return self
                def fetchone(self): return (1,)
                def close(self): pass

            class FakeStore:
                def __init__(self, _path): self.db = FakeDB()
                def job(self, _ident): return job
                def artifact(self, _ident): return {"payload": {"completion": {"binding": {}}}}

            with (patch("batch_pipeline.store.Store", FakeStore),
                  patch("worker_exchange.execution_manifest.validate", return_value={
                      "cases": [{"case_id": case, "kind": "delivery"}]}),
                  patch("worker_exchange.delivery_handoff.validate_case"),
                  patch("recording_store.stored_attempt_path", return_value=attempt),
                  patch("batch_pipeline.completion.verify"),
                  patch("worker_exchange.media.audit"),
                  patch("organize_work.refresh_workspaces")):
                audit["passed"] = False
                write(attempt / "audit.json", audit)
                with self.assertRaisesRegex(ValueError, "audit incomplete"):
                    accept(root, self.repo, "batch", db, "run", self.aid,
                           case, 7, 1, attempt / "audit.json")
                self.assertEqual(read(root / "sets/full-train/selection.json")["members"], [])
                audit["passed"] = True
                write(attempt / "audit.json", audit)
                accepted = accept(root, self.repo, "batch", db, "run", self.aid,
                                  case, 7, 1, attempt / "audit.json")
            self.assertEqual(accepted["accepted_in"], ["full-train"])
            self.assertEqual(read(root / "sets/full-train/selection.json")["members"][0]["recording_id"], rid)

    acceptance = "test_local_acceptance_references_one_recording_in_both_sets"
    setattr(ScopedAcceptance, acceptance, getattr(DeliveryHandoffTests, acceptance).__wrapped__)
    suite.addTest(ScopedAcceptance(acceptance))
    suite.addTest(ScopedAcceptance("test_training_target_acceptance"))
    output = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="worker-local-delivery-lock-") as temporary:
        with patch.object(runtime_dependencies, "lock_path",
                          return_value=Path(temporary) / "runtime-edit.lock"):
            result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    if result.errors or result.failures or result.skipped or result.testsRun != 4:
        raise RuntimeError("Local campaign integration did not execute and pass:\n" + output.getvalue())
    return {"scenario": "primary_fallback_preparation_exact_dispatch_rejected_audit_and_testing_and_training_acceptance",
            "executed": True, "tests_run": result.testsRun,
            "synthetic_fixture": True, "output_tail": output.getvalue().strip().splitlines()[-1]}


def main():
    checks = [
        ("portable_exact_fallback_materialization", "tests.test_worker_candidates.CandidateTests.test_selects_exact_fallback_and_records_identity"),
        ("portable_tampered_candidate_rejection", "tests.test_worker_candidates.CandidateTests.test_rejects_unknown_and_tampered_candidate"),
        ("selected_saved_processing_negative", "tests.test_worker_candidates.CandidateTests.test_saved_processing_rejects_mismatched_selection_before_conversion"),
    ]
    results = [run(name, [sys.executable, "-m", "unittest", target]) for name, target in checks]
    results.append(run_campaign())
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
                      "reason": "Campaign integration executed with synthetic fixtures; live saved-source rerun and physical full-train acceptance remain unproved. The saved-source rerun needs ffmpeg, which is absent on this host",
                      "scenarios": results}, indent=2))


if __name__ == "__main__":
    main()
