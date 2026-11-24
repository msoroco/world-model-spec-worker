import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import finalize
from native_acquisition import seal_original_acquisition


CASE = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator__reference"


class AnalysisTests(unittest.TestCase):
    def _attempt(self, base):
        rows = [{"frame_id": 1000 + i, "time_s": round(i / 20, 2),
                 "velocity_mps": [3.0, 0.0, 0.0], "x_m": -30 + 3 * i / 20,
                 "y_m": -.75} for i in range(900)]
        context = {"case_id": CASE, "source_kind": "original_local_native_capture",
                   "jurisdiction": {"city_of_las_vegas": True, "source": "fixture map packet"},
                   "bicycle_classification": {"human_powered": True, "moped": False,
                                              "source": "fixture asset packet"},
                   "alley_route": {"source": "fixture road geometry"},
                   "rack_geometry": {"source": "fixture actor vertices"},
                   "samples": [{"frame": row["frame_id"], "time_s": row["time_s"],
                                "weather": "clear", "surface": "dry", "visibility": "clear",
                                "pedestrians": "none near rack", "curvature": "straight"}
                               for row in rows]}
        packet = base / "source-context.json"
        packet.write_text(json.dumps(context))
        attempt = base / "attempt"
        seal_original_acquisition(attempt, CASE, rows, context,
                                  context_source={"path": str(packet),
                                                  "sha256": hashlib.sha256(packet.read_bytes()).hexdigest()})
        (attempt / "config.json").write_bytes((ROOT / "config.json").read_bytes())
        return attempt

    def test_full_window_measured_without_legal_label(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = self._attempt(Path(directory))
            report = finalize(attempt)
            self.assertEqual(len(report["measurements"]["actual_bicycle_speed_history"]["value"]), 900)
            self.assertEqual(report["summary"]["mean_speed_mps"], 3.0)
            self.assertEqual(report["legal_prudence"], "unresolved")

    def test_missing_case_source_and_stale_hash_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = self._attempt(Path(directory))
            (attempt / "context.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "stale required source"):
                finalize(attempt)
            (attempt / "context.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: context.json"):
                finalize(attempt)


if __name__ == "__main__":
    unittest.main()
