"""The exact offline bundle stays synthetic and source-hashed."""
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_offline_diagnostic import build_bundle


class OfflineDiagnosticTests(unittest.TestCase):
    def test_single_exact_synthetic_bundle(self):
        manifest_path, case_id = build_bundle()
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


if __name__ == "__main__":
    unittest.main()
