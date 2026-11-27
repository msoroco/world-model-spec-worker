"""CPU proof of saved original channel publication and negative frame join."""
import json
import tempfile
import unittest
from pathlib import Path

from beam_publication import CHANNELS, publish
from test_analysis import CASE, TEMP_ROOT, fixture


def _finish_fixture(root):
    fixture(root)
    states = [json.loads(x) for x in (root / "actor-state.jsonl").read_text().splitlines()]
    trace = []
    video = []
    for index, state in enumerate(states):
        frame = state["frame"]
        trace.append({"frame": frame, "time_s": state["time_s"],
                      "position_m": state["actors"]["ego"]["center_m"],
                      "speed_mps": state["actors"]["ego"]["speed_mps"]})
        video.append({"video_frame": index, "carla_frame": frame,
                      "time_s": state["time_s"]})
    (root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
    (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in video))
    construction = {"case_id": CASE["case_id"], "recording_description": {
        "channels": [{"name": name, "unit": "structured record"} for name in CHANNELS],
        "context_inputs": [], "limitations": ["CPU diagnostic only"]}}
    (root / "construction.json").write_text(json.dumps(construction) + "\n")


class PublicationTests(unittest.TestCase):
    def setUp(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="publication-", dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _finish_fixture(self.root)

    def test_saved_channels_and_result(self):
        result = publish(self.root, expected_frames=9, diagnostic=True)
        self.assertEqual(result["case_id"], CASE["case_id"])
        self.assertEqual({x["name"] for x in result["recording_evidence"]}, set(CHANNELS))
        self.assertEqual(result["measured_values"]["frame_count"], 9)
        self.assertFalse(result["physical_acceptance_claimed"])
        for name in CHANNELS:
            self.assertEqual(len((self.root / (name + ".jsonl")).read_text().splitlines()), 9)

    def test_mismatched_video_frame_rejected_before_publication(self):
        path = self.root / "video_frames.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        rows[1]["carla_frame"] += 2
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        with self.assertRaisesRegex(ValueError, "frame and time join"):
            publish(self.root, expected_frames=9, diagnostic=True)
        self.assertFalse((self.root / "original_actor_state.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
