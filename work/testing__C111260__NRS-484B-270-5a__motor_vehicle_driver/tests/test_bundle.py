import json
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("c111260_runner", ROOT / "runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class BundleTest(unittest.TestCase):
    def test_exact_selection(self):
        root = Path(__file__).resolve().parents[1]
        selected = runner.check(root)
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(selected, config["case"]["case_id"])
        self.assertEqual(len(config["supported_case_ids"]), 6)

    def test_rejects_case_drift(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        config["case"]["motorist_response"] = "unknown"
        import tempfile
        with tempfile.TemporaryDirectory() as scratch:
            (Path(scratch) / "config.json").write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, "selected rider and response"):
                runner.check(scratch)


if __name__ == "__main__":
    unittest.main()
