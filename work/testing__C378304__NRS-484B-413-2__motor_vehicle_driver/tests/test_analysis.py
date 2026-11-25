import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import build_report


class SavedFinalizerTests(unittest.TestCase):
    def test_missing_or_diagnostic_source_cannot_finalize(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.json").write_text(json.dumps({
                "selected_case_id": "a__short80"}) + "\n")
            (root / "acquisition.json").write_text(json.dumps({
                "original-site.json": {"kind": "diagnostic_fixture", "sha256": "0" * 64}}) + "\n")
            (root / "original-site.json").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "Missing required source: original-site.json"):
                build_report(root)
            (root / "acquisition.json").unlink()
            with self.assertRaises(FileNotFoundError):
                build_report(root)


if __name__ == "__main__":
    unittest.main()
