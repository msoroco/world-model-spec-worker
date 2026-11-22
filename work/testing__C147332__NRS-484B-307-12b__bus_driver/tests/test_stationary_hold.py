"""Source-bound stopped bus and tamper negatives on CPU fixtures."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from stationary_hold import audit
from test_comparison_audit import make_attempt, sha


class StationaryHoldTest(unittest.TestCase):
    def test_measured_hold_and_motion_brake_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory) / "stand"
            make_attempt(attempt, "red_lane_stand")
            trace = [{"frame": frame, "time_s": frame / 20,
                      "position_m": [0, -1.8, 0], "speed_mps": 0.0}
                     for frame in (1, 2)]
            controls = [{"frame": frame, "elapsed_seconds": frame / 20,
                         "requested_control": {"brake": 1.0, "throttle": 0.0}}
                        for frame in (1, 2)]
            mapping = [{"video_frame": frame - 1, "carla_frame": frame,
                        "time_s": frame / 20} for frame in (1, 2)]
            for name, rows in (("trace.jsonl", trace),
                               ("controller-history.jsonl", controls),
                               ("video_frames.jsonl", mapping)):
                (attempt / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
            acquisition = json.loads((attempt / "acquisition.json").read_text())
            for name in ("trace.jsonl", "controller-history.jsonl", "video_frames.jsonl"):
                acquisition[name] = sha(attempt / name)
            (attempt / "acquisition.json").write_text(json.dumps(acquisition))
            self.assertEqual(audit(attempt)["status"], "stationary_hold_measured")
            trace[1]["speed_mps"] = 2.0
            (attempt / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
            acquisition["trace.jsonl"] = sha(attempt / "trace.jsonl")
            (attempt / "acquisition.json").write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, "measured speed"):
                audit(attempt)
            trace[1]["speed_mps"] = 0.0
            (attempt / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
            acquisition["trace.jsonl"] = sha(attempt / "trace.jsonl")
            (attempt / "acquisition.json").write_text(json.dumps(acquisition))
            controls[1]["requested_control"]["brake"] = 0.0
            (attempt / "controller-history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in controls))
            acquisition["controller-history.jsonl"] = sha(attempt / "controller-history.jsonl")
            (attempt / "acquisition.json").write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, "brake hold"):
                audit(attempt)


if __name__ == "__main__":
    unittest.main()
