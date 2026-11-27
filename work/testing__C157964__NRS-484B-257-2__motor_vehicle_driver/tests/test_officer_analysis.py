import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import build
from officer_native_capture import capture
from test_officer_native_capture import CaptureAdapter
import test_officer_site_packet


ROOT = Path(__file__).resolve().parents[1]


class MotionAdapter(CaptureAdapter):
    def tick_and_read(self, actors, cameras):
        sample = super().tick_and_read(actors, cameras)
        i = self.index - 1
        sample["state"] = {
            "ego": {"id": "ego", "speed_mps": 2.0,
                    "leading_station_m": -10 + i * .1,
                    "across_or_within": i >= 100},
            "other": {"id": "other", "center_station_m": 0.0,
                      "phase": "within" if i <= 500 else "cleared"},
            "officer": {"id": "officer", "controls_traffic": True,
                        "visible": True, "directive": "stop"},
            "officer_directive": "stop"}
        return sample


class SavedOfficerAnalysisTest(unittest.TestCase):
    def attempt(self, root):
        packet = test_officer_site_packet.OfficerSitePacketTest().packet(root)
        attempt = root / "attempt"
        attempt.mkdir()
        case_root = ROOT / "cases/occupied_stop"
        shutil.copy2(case_root / "construction.json", attempt / "construction.json")
        shutil.copy2(case_root / "config.json", attempt / "config.json")
        shutil.copy2(ROOT / "runner.py", attempt / "runner.py")
        config = json.loads((attempt / "config.json").read_text())
        adapter = MotionAdapter()
        capture(adapter, config, packet, attempt)
        seal_path = attempt / "capture-seal.json"
        seal = json.loads(seal_path.read_text())
        seal["diagnostic_fixture"] = True
        seal_path.write_text(json.dumps(seal))
        review = {"case_id": config["selected_case_id"],
                  "source_kind": "synthetic_review",
                  "reviewer_id": "fixture reviewer only",
                  "raw_video_sha256": hashlib.sha256((attempt / "raw.mkv").read_bytes()).hexdigest(),
                  "officer_visible": True, "officer_controlling_traffic": True,
                  "observed_directive": "stop", "crossing_interval_frames": [95, 300]}
        (attempt / "original-attempt/officer-review.json").write_text(json.dumps(review))
        return attempt

    def test_original_saved_sources_derive_no_legal_verdict(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as temp:
            attempt = self.attempt(Path(temp))
            report, result = build(attempt)
            self.assertTrue(report["analysis_complete"])
            self.assertFalse(report["legal_verdict_claimed"])
            self.assertEqual(result["measured_values"]["motion"]["observed_other_phase_at_entry"],
                             "within")
            self.assertIsNone(result["measured_values"]["motion"]["legal_judgment"])

    def test_missing_independent_officer_review_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as temp:
            attempt = self.attempt(Path(temp))
            (attempt / "original-attempt/officer-review.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                build(attempt)

    def test_stale_original_frame_map_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work") as temp:
            attempt = self.attempt(Path(temp))
            path = attempt / "original-attempt/frame-map.json"
            path.write_text(path.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "sealed original source changed"):
                build(attempt)


if __name__ == "__main__":
    unittest.main()
