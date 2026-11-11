import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import FrameMap

spec = importlib.util.spec_from_file_location("capture_sources", ROOT / "capture_sources.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CaptureTests(unittest.TestCase):
    def test_original_velocity_and_frame_map_written_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subject = NS(id=12,
                         get_velocity=lambda: NS(x=35.7632, y=0, z=0),
                         get_transform=lambda: NS(location=NS(x=50, y=1.75, z=0),
                                                  rotation=NS(yaw=0)))
            with FrameMap(root / "video_frames.jsonl") as mapping, \
                 (root / "subject_motion.jsonl").open("w") as motion, \
                 (root / "trace.jsonl").open("w") as trace:
                first = module.record_sample(mapping, motion, trace, subject,
                    NS(frame=100, timestamp=NS(elapsed_seconds=1.0)))
                self.assertEqual(first["video_frame"], 0)
                module.record_sample(mapping, motion, trace, subject,
                    NS(frame=101, timestamp=NS(elapsed_seconds=1.05)))
            rows = [json.loads(line) for line in (root / "subject_motion.jsonl").read_text().splitlines()]
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            self.assertEqual(rows[0]["velocity_mps"], [35.7632, 0.0, 0.0])
            self.assertEqual([f["carla_frame"] for f in frames], [100, 101])
            self.assertEqual(len((root / "trace.jsonl").read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
