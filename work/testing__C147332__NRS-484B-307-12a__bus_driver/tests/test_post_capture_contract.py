"""Recorded-only handoff binds exact positive and negative saved fixture logs."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from bind_post_capture import handoff, sha


class PostCaptureContractTests(unittest.TestCase):
    def setUp(self):
        manifest = json.loads((ROOT / "execution-manifest.json").read_text())
        self.entries = manifest["cases"]

    def test_four_exact_saved_handoffs_are_bound(self):
        for entry in self.entries:
            with self.subTest(case=entry["case_id"]):
                proof = handoff(entry)
                self.assertTrue(proof["recorded_only"])
                self.assertIn("runtime.py process-saved", proof["command"])
                self.assertIn("--case " + entry["case_id"], proof["command"])
                self.assertEqual(proof["test_log_sha256"], sha(ROOT / proof["test_log"]))
                fallback = proof["fallback1_fixture"]
                self.assertEqual(fallback["test_log_sha256"], sha(ROOT / fallback["test_log"]))

    def test_missing_negative_result_is_rejected(self):
        entry = self.entries[0]
        kind = entry["case_id"].rsplit("__", 1)[-1]
        scratch = REPO / ".runtime-work" / "c147332-post-capture-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            for candidate in ("primary", "fallback1"):
                name = f"cpu-camera-sync-saved-{kind}-{candidate}.log"
                shutil.copyfile(ROOT / name, root / name)
            (root / f"cpu-camera-sync-saved-{kind}-fallback1.log").write_text(
                f"{entry['case_id']} fallback1 positive passed\n")
            with self.assertRaisesRegex(ValueError, "fixture result differs"):
                handoff(entry, root=root)


if __name__ == "__main__":
    unittest.main()
