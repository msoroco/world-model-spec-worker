import importlib.util
import json
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "build_gpu_queue.py"
spec = importlib.util.spec_from_file_location("build_gpu_queue", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n" if not isinstance(value, str) else value)


class CanonicalQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.aid = "heldout__C1__LAW__driver"
        self.case = self.aid + "__one"
        self.folder = self.repo / "work" / self.aid
        write(self.repo / "batch.json", {"batch_id": "B", "assignments": {self.aid: {}}})
        write(self.folder / "result.json", {"status": "ready",
                                             "readiness_kind": "delivery_prepared"})
        write(self.folder / "construction.json", "primary\n")
        write(self.folder / "fallback.json", "fallback\n")
        write(self.folder / "delivery_audit.py", "print('audit')\n")
        write(self.folder / "audit.log", "audit passed\n")
        entry = {"case_id": self.case, "construction": "construction.json",
                 "construction_sha256": digest(self.folder / "construction.json"),
                 "candidates": [{"id": "fallback1", "construction": "fallback.json",
                                 "construction_sha256": digest(self.folder / "fallback.json")}],
                 "delivery_acceptance": {
                     "case_id": self.case, "script": "delivery_audit.py",
                     "script_sha256": digest(self.folder / "delivery_audit.py"),
                     "test_log": "audit.log", "test_log_sha256": digest(self.folder / "audit.log"),
                     "test_exit_code": 0, "command": f"python delivery_audit.py --case {self.case}"}}
        write(self.folder / "execution-manifest.json",
              {"assignment_id": self.aid, "cases": [entry]})
        write(self.folder / "case-plan.json",
              {"assignment_id": self.aid, "cases": [{"case_id": self.case}],
               "comparisons": [{"comparison_id": "contrast", "case_ids": [self.case]}]})
        source = {"assignment_id": self.aid,
                  "execution_manifest_sha256": digest(self.folder / "execution-manifest.json"),
                  "case_plan_sha256": digest(self.folder / "case-plan.json"),
                  "cases": [{"case_id": self.case,
                             "construction_sha256": entry["construction_sha256"],
                             "candidate_commands": {"fallback1": "capture fallback1"},
                             "capture_command": "capture " + self.case,
                             "postprocessing_command": "process-saved " + self.case,
                             "additional_source_audit_command": (
                                 "python delivery_audit.py --case " + self.case +
                                 ' --attempt "$ATTEMPT" --output "$AUDIT_OUTPUT"')}],
                  "comparisons": [{"comparison_id": "contrast", "case_ids": [self.case],
                                   "audit_command": f"python audit.py {self.aid} contrast"}]}
        write(self.folder / "gpu-queue.json", source)

    def test_builds_exact_local_commands_and_fallback(self):
        queue = module.build(self.repo)
        self.assertEqual(len(queue["cases"]), 1)
        row = queue["cases"][0]
        self.assertIn("prepare-delivery", row["candidate_commands"]["fallback1"])
        self.assertIn("--candidate fallback1", row["candidate_commands"]["fallback1"])
        self.assertIn("owner-released", row["owner_release_command"])
        self.assertIn("--case " + self.case, row["execute_command"])
        self.assertEqual(queue["comparison_audit_commands"][0]["comparison_id"], "contrast")

    def test_rejects_partial_and_changed_source(self):
        result_path = self.folder / "result.json"
        write(result_path, {"status": "partial"})
        with self.assertRaisesRegex(ValueError, "not delivery ready"):
            module.build(self.repo)
        write(result_path, {"status": "ready", "readiness_kind": "delivery_prepared"})
        write(self.folder / "construction.json", "changed\n")
        with self.assertRaisesRegex(ValueError, "Stale construction"):
            module.build(self.repo)

    def test_rejects_missing_comparison_auditor(self):
        path = self.folder / "gpu-queue.json"
        source = json.loads(path.read_text())
        del source["comparisons"][0]["audit_command"]
        write(path, source)
        with self.assertRaisesRegex(ValueError, "Missing exact executable comparison"):
            module.build(self.repo)

    def test_includes_branch_coverage_additional_binding(self):
        write(self.repo / "work/_shared/branch-coverage.json",
              {"additional_bindings": [{"assignment_id": "heldout__extra__LAW__driver"}]})
        with self.assertRaisesRegex(ValueError, "Missing result: heldout__extra"):
            module.build(self.repo)


if __name__ == "__main__":
    unittest.main()
