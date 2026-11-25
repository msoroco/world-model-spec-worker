"""Reject a saved trace or frame map that diverges from sealed Native events."""
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_delivery_prepared import join_original_frames


class OriginalFrameJoinTests(unittest.TestCase):
    def setUp(self):
        self.events = [{"frame": 100 + i, "time_s": i / 20} for i in range(900)]
        self.trace = [{"frame": 100 + i, "time_s": i / 20} for i in range(900)]
        self.mapping = [{"video_frame": i, "carla_frame": 100 + i,
                         "time_s": i / 20} for i in range(900)]

    def test_full_original_join(self):
        join_original_frames(self.events, self.trace, self.mapping)

    def test_rejects_middle_event_trace_or_map_divergence(self):
        self.trace[450]["frame"] += 1
        with self.assertRaisesRegex(ValueError, "event/trace/video"):
            join_original_frames(self.events, self.trace, self.mapping)
        self.trace[450]["frame"] -= 1
        self.mapping[450]["time_s"] += 0.05
        with self.assertRaisesRegex(ValueError, "event/trace/video"):
            join_original_frames(self.events, self.trace, self.mapping)
        self.mapping[450]["time_s"] -= 0.05
        self.mapping[450]["video_frame"] = 449
        with self.assertRaisesRegex(ValueError, "event/trace/video"):
            join_original_frames(self.events, self.trace, self.mapping)

    def test_rejects_short_history(self):
        with self.assertRaisesRegex(ValueError, "Full saved frame"):
            join_original_frames(self.events[:-1], self.trace, self.mapping)


if __name__ == "__main__":
    unittest.main()
