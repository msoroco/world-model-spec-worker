"""Source-shaped 600-frame saved measurement and rejection checks."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from saved_measure import VIDEOS, measure
from source_review import ASSIGNMENT, SOURCES


def write_json(path, value):
    path.write_text(json.dumps(value) + "\n")


class SavedMeasureTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.case = ASSIGNMENT + "__probe_01"
        context = self.root / "source_context"
        context.mkdir()
        refs = {}
        for name in SOURCES:
            path = context / (name + ".txt")
            path.write_text("Synthetic diagnostic " + name + "\n")
            refs[name] = {"path": "source_context/" + name + ".txt",
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        write_json(self.root / "emergency-review.json",
                   {"assignment_id": ASSIGNMENT, "case_id": self.case,
                    "review_kind": "synthetic_diagnostic", "sources": refs})
        video_hashes = {}
        for name in VIDEOS:
            path = self.root / name
            path.write_bytes(b"synthetic video placeholder " + name.encode())
            video_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        lamp = [{"frame": i, "qualifying_flashes_visible": True} for i in range(600)]
        signal = [{"frame": i, "hand_signal_visible": False,
                   "officer_direction_visible": False} for i in range(600)]
        for name, frames in (("lamp", lamp), ("signal", signal)):
            write_json(self.root / (name + "-pixel-review.json"),
                       {"case_id": self.case, "review_kind": "synthetic_diagnostic",
                        "video_sha256": video_hashes, "frames": frames})
        with (self.root / "video_frames.jsonl").open("w") as fmap, \
                (self.root / "emergency-native.jsonl").open("w") as trace:
            for i in range(600):
                fmap.write(json.dumps({"video_frame": i, "native_frame": i + 100,
                                       "time_s": i / 20}) + "\n")
                trace.write(json.dumps({"frame": i, "native_frame": i + 100,
                    "t_s": i / 20, "ego": {"actor_id": 1, "lane_id": -3 if i >= 160 else -2,
                                              "x_m": -85 + i * .2},
                    "emergency": {"actor_id": 2, "lane_id": -1,
                                  "x_m": -20 + i * .06, "speed_mps": 1.2}}) + "\n")

    def test_move_over_frame_join(self):
        result = measure(self.root, self.case, diagnostic=True)
        self.assertEqual(result["frame_count"], 600)
        self.assertTrue(result["active_adjacent_frames"])
        self.assertTrue(result["active_nonadjacent_frames"])
        self.assertIsNone(result["lane_change_safe"])
        self.assertIsNone(result["legal_result"])

    def test_original_source_and_missing_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "Original Native"):
            measure(self.root, self.case)
        (self.root / "source_context" / "vehicle_authorization.txt").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source"):
            measure(self.root, self.case, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
