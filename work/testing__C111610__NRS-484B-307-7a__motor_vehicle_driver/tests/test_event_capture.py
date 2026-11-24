import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import aspect_capture
import event_capture
import saved_aspect


class EventCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.site = {"official_head_id": "17", "ego_approach_id": "north",
                     "arrow_movement": "left"}
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def step(self, i):
        self.calls.append(i)
        lit = (i // 10) % 2 == 0
        aspect = {"frame": 100 + i, "elapsed_seconds": i / 20,
                  "head_id": "17", "facing_approach_id": "north",
                  "arrow_color": "yellow", "arrow_direction": "left",
                  "arrow_lit": lit, "source_kind": "display_sensor",
                  "source_id": "head-camera-17", "native_head_state": "Yellow",
                  "concurrent_indications": []}
        event = {"frame": 100 + i, "official_head_id": "17",
                 "facing_approach_id": "north", "arrow_movement": "left",
                 "concurrent_indications": [],
                 "lit_aspects": ["flashing_yellow_turn_arrow"] if lit else [],
                 "ego_xy": [0.0, float(i)], "other_users": []}
        return aspect, event

    def test_one_tick_pair_and_saved_replay(self):
        receipt = event_capture.capture_pair(self.site, self.root, self.step)
        self.assertEqual(self.calls, list(range(900)))
        self.assertTrue(receipt["event_aspect_join"])
        self.assertEqual(receipt["frame_count"], 900)
        self.assertTrue(saved_aspect.join_event_history(
            self.site, self.root, receipt["event_ref"])["event_aspect_join"])
        with self.assertRaisesRegex(aspect_capture.AspectError, "already exists"):
            event_capture.capture_pair(self.site, self.root, self.step)
        (self.root / receipt["event_ref"]["path"]).write_text("tampered")
        with self.assertRaisesRegex(aspect_capture.AspectError, "hash mismatch"):
            saved_aspect.join_event_history(self.site, self.root,
                                            receipt["event_ref"])

    def test_rejects_display_mismatch_before_writing(self):
        def wrong(i):
            aspect, event = self.step(i)
            if i == 13:
                event["lit_aspects"] = ["flashing_yellow_turn_arrow"]
            return aspect, event
        with self.assertRaisesRegex(aspect_capture.AspectError, "display mismatch"):
            event_capture.capture_pair(self.site, self.root, wrong)
        self.assertFalse((self.root / "arrow-events-original.json").exists())
        self.assertFalse((self.root / "arrow-aspect-original.json").exists())


if __name__ == "__main__":
    unittest.main()
