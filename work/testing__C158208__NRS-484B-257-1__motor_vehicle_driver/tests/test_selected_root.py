import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner


class SelectedRootTests(unittest.TestCase):
    def test_all_selected_candidates_are_source_gated(self):
        import json

        manifest = json.loads((runner.HERE / "execution-manifest.json").read_text())
        self.assertEqual(len(manifest["cases"]), 11)
        for entry in manifest["cases"]:
            self.assertEqual(runner.selected(entry["case_id"], "primary"), entry)
            self.assertEqual(runner.selected(entry["case_id"], "fallback1"),
                             entry["candidates"][0])

    def test_original_source_is_required_before_materialization(self):
        import json

        manifest = json.loads((runner.HERE / "execution-manifest.json").read_text())
        case_id = manifest["cases"][0]["case_id"]
        with patch.dict("os.environ", {}, clear=True):
            with patch("sys.argv", ["runner.py", "--case", case_id,
                                    "--output-dir", "uncreated-attempt"]):
                with self.assertRaisesRegex(ValueError, "source-hashed reviewed"):
                    runner.main()


if __name__ == "__main__":
    unittest.main()
