import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture_finalize import close_capture


class CaptureFinalizeTests(unittest.TestCase):
    def test_refuses_diagnostic_capture_and_unrestored_world(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "original Native capture"):
                close_capture(root, {"source_kind": "synthetic_fixture",
                                     "world_restore": {"restored": True}})
            with self.assertRaisesRegex(ValueError, "verified world restore"):
                close_capture(root, {"source_kind": "original_capture",
                                     "world_restore": {"restored": False}})
            self.assertFalse((root / "capture-seal.json").exists())


if __name__ == "__main__":
    unittest.main()
