import importlib.util
import pathlib
import shutil
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("c111260_analysis", ROOT / "analysis.py")
import sys
sys.path.insert(0, str(ROOT))
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)
from test_saved_encounter import attempt


class AnalysisTests(unittest.TestCase):
    def _attempt(self, path):
        attempt(path)
        shutil.copyfile(ROOT / "config.json", path / "config.json")
        (path / "video_frames.jsonl").write_text("original mapping source\n")
        for camera in ("overview", "approach", "reference_corner", "driver_reference"):
            (path / (camera + ".mkv")).write_bytes(b"source-video")

    def test_saved_measurements_and_unresolved_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary)
            self._attempt(path)
            report = ANALYSIS.finalize(path, path / "analysis-report.json")
            self.assertEqual(report["measurement"]["rider_kind"], "bicycle")
            self.assertFalse(report["physical_completion"])
            self.assertTrue((path / "result.json").is_file())

    def test_missing_exact_source_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary)
            self._attempt(path)
            (path / "history.json").unlink()
            with self.assertRaisesRegex(ValueError, "source"):
                ANALYSIS.finalize(path, path / "analysis-report.json")


if __name__ == "__main__":
    unittest.main()
