import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SavedFeedbackTests(unittest.TestCase):
    def test_exact_saved_path_reports_missing_case_source_without_replay(self):
        construction = json.loads((ROOT / "construction.json").read_text())
        cid = construction["case_id"]
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            (base / "construction.json").write_text(json.dumps(construction))
            runtime_source = next((p / "runtime/SOURCE-MANIFEST.json" for p in ROOT.parents
                                   if (p / "runtime/SOURCE-MANIFEST.json").is_file()), None)
            self.assertIsNotNone(runtime_source)
            manifest = {"runtime_manifest_sha256": __import__("hashlib").sha256(
                            runtime_source.read_bytes()).hexdigest(),
                        "cases": [{"case_id": cid, "construction": "construction.json",
                                   "construction_sha256": __import__("hashlib").sha256(
                                       (base / "construction.json").read_bytes()).hexdigest(),
                                   "measurement_procedure": {"entrypoint": "finalize.py"}}]}
            (base / "manifest.json").write_text(json.dumps(manifest))
            attempt = base / "attempt"
            attempt.mkdir()
            for item in construction["files"]:
                target = attempt / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item["content"])
            (attempt / "construction.json").write_text(json.dumps(construction))
            (attempt / "raw.mkv").write_text("diagnostic file; no video decode is claimed")
            (attempt / "acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}))
            library = None
            for parent in ROOT.parents:
                candidate = parent / "runtime/library"
                if candidate.is_dir():
                    library = candidate
                    runtime_py = parent / "runtime.py"
                    break
            self.assertIsNotNone(library)
            command = [sys.executable, str(runtime_py), "process-saved", "--manifest", str(base / "manifest.json"),
                       "--case", cid, "--attempt", str(attempt), "--output", str(base / "derived"),
                       "--library", str(library), "--validator", str(base / "unused-validator")]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout)
            self.assertTrue(receipt["recorded_only"])
            self.assertTrue(receipt["missing_evidence"])
            feedback = json.loads((base / "derived/v0001/feedback.json").read_text())
            self.assertFalse(feedback["native_replay_requested"])
            self.assertIn("following_samples.jsonl", feedback["error"])


if __name__ == "__main__":
    unittest.main()
