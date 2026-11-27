import importlib.util
from pathlib import Path
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("angle_analysis", ROOT / "analysis.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SavedAnalysisTests(unittest.TestCase):
    def test_missing_and_stale_original_sources_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                module.verified(root, "trace.jsonl", {})
            trace = root / "trace.jsonl"
            trace.write_text('{"frame": 1}\n')
            with self.assertRaisesRegex(ValueError, "stale original Native source"):
                module.verified(root, "trace.jsonl", {"trace.jsonl": {"kind": "original_native", "sha256": "0" * 64}})
            actual = {"trace.jsonl": {"kind": "original_native", "sha256": module.sha(trace)}}
            self.assertEqual(module.verified(root, "trace.jsonl", actual), trace)
            trace.write_text('{"frame": 2}\n')
            with self.assertRaisesRegex(ValueError, "stale original Native source"):
                module.verified(root, "trace.jsonl", actual)


if __name__ == "__main__":
    unittest.main()
