import importlib.util
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "native_capture.py"
spec = importlib.util.spec_from_file_location("native_capture", MODULE)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class NativeReleaseTests(unittest.TestCase):
    def test_source_hashed_training_requests_select_distinct_start_delays(self):
        self.assertEqual(capture.release_frames(-2.860000042617321),
                         {"ego": 0, "other": 57})
        self.assertEqual(capture.release_frames(-0.02500000037252903),
                         {"ego": 0, "other": 1})
        self.assertEqual(capture.release_frames(2.810000041872263),
                         {"ego": 56, "other": 0})
        with self.assertRaisesRegex(ValueError, "finite requested"):
            capture.release_frames(float("nan"))


if __name__ == "__main__":
    unittest.main()
