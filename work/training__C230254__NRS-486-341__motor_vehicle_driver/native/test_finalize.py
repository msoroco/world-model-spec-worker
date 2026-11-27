import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from acquire_lane_use import sample
from finalize import finalize
from test_acquire_lane_use import actor, road
from test_comparison_audit import make_case


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


class SavedRuntimeFinalizerTest(unittest.TestCase):
    def test_full_window_and_missing_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "attempt"
            make_case(root, "full_lane_available", "full_lane_available", 4)
            config = json.loads((HERE / "config-full_lane_available.json").read_text())
            (root / "config.json").write_text(json.dumps(config) + "\n")
            refs = {"actor_trace": "trace.jsonl", "actor_bounds": "lane-use-source.jsonl",
                    "lane_map": "lane-use-source.jsonl"}
            with (root / "lane-use-source.jsonl").open("w") as source, \
                    (root / "video_frames.jsonl").open("w") as mapping, \
                    (root / "trace.jsonl").open("w") as trace:
                for index in range(600):
                    native_frame = index + 25
                    elapsed = index / 20
                    x = index * 0.05
                    row = sample(road(), actor(1, x, 4), actor(2, x, 0, width=1),
                                 frame=index, native_frame=native_frame,
                                 time_s=elapsed, source_refs=refs)
                    source.write(json.dumps(row) + "\n")
                    mapping.write(json.dumps({
                        "video_frame": index, "carla_frame": native_frame,
                        "native_frame": native_frame, "time_s": elapsed,
                        "camera_native_frames": {name: native_frame for name in
                                                 ("overview", "approach", "reference_corner",
                                                  "driver_reference")}}) + "\n")
                    trace.write(json.dumps({"frame": native_frame, "time_s": elapsed,
                                            "position_m": [x, 4, 0]}) + "\n")
            previous = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
            os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(Path(directory).resolve())
            sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
            try:
                original_geometry = (root / "lane-use-source.jsonl").read_text()
                (root / "lane-use-source.jsonl").unlink()
                with self.assertRaisesRegex(ValueError, "Missing required source"):
                    finalize(root, Path(directory) / "negative-report.json")
                shutil.rmtree(root / "channels")
                (root / "lane-use-source.jsonl").write_text(original_geometry)
                report = finalize(root, Path(directory) / "report.json")
                self.assertTrue(report["analysis_complete"])
                self.assertFalse(report["legal_verdict_claimed"])
                self.assertEqual(json.loads((root / "result.json").read_text())
                                 ["measured_values"]["frame_count"], 600)
            finally:
                sys.path.remove(str(REPO / "runtime/scenario_pipeline"))
                if previous is None:
                    os.environ.pop("SCENARIO_PIPELINE_OUTPUT_ROOT", None)
                else:
                    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = previous


if __name__ == "__main__":
    unittest.main()
