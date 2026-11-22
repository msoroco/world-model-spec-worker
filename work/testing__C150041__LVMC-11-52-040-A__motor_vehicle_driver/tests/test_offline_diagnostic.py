"""The exact offline bundle stays synthetic and source-hashed."""
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_offline_diagnostic import KINDS, build_bundle


class OfflineDiagnosticTests(unittest.TestCase):
    def test_six_exact_synthetic_bundles_and_short_approach_fallbacks(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                manifest_path, case_id = build_bundle(kind)
                manifest = json.loads(manifest_path.read_text())
                self.assertTrue(manifest["diagnostic_only"])
                entry = manifest["cases"][0]
                self.assertEqual(entry["case_id"], case_id)
                construction_path = manifest_path.parent / entry["construction"]
                self.assertEqual(entry["construction_sha256"],
                                 hashlib.sha256(construction_path.read_bytes()).hexdigest())
                construction = json.loads(construction_path.read_text())
                self.assertEqual(construction["source_kind"], "synthetic_offline_protocol_fixture_only")
                self.assertEqual(construction["entrypoint"], "runner.py")
                self.assertTrue(any(item["path"] == "tests/test_offline.py" for item in construction["files"]))
                self.assertTrue(any("cannot launch Native capture" in item["content"]
                                    for item in construction["files"] if item["path"] == "runner.py"))
                self.assertEqual(entry["candidate_risk"]["status"], "physical")
                self.assertEqual(len(entry["candidates"]), 1)
                candidate = entry["candidates"][0]
                self.assertEqual(candidate["id"], "fallback1")
                fallback_path = manifest_path.parent / candidate["construction"]
                self.assertEqual(candidate["construction_sha256"],
                                 hashlib.sha256(fallback_path.read_bytes()).hexdigest())
                fallback = json.loads(fallback_path.read_text())
                self.assertEqual(fallback["case_id"], construction["case_id"])
                primary_files = {item["path"]: item["content"] for item in construction["files"]}
                fallback_files = {item["path"]: item["content"] for item in fallback["files"]}
                self.assertEqual(primary_files.keys(), fallback_files.keys())
                self.assertEqual(primary_files["config.json"], fallback_files["config.json"])
                self.assertIn('"--approach-distance-m", "6.0"', fallback_files["runner.py"])
                self.assertNotEqual(primary_files["scene.json"], fallback_files["scene.json"])


if __name__ == "__main__":
    unittest.main()
