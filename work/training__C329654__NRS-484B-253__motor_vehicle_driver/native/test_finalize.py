"""Saved finalizer source contract checks without Native or invented footage."""
import json
import tempfile
import unittest
from pathlib import Path

from finalize import measure_yield_sequence, required, source_join


class FinalizerSourceTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)

    def test_missing_case_specific_source(self):
        with self.assertRaisesRegex(ValueError,
                                    "Missing required source: left-turn-actors.jsonl"):
            measure_yield_sequence(self.root, {"measured": {}})

    def test_missing_original_trace_rejected(self):
        (self.root / "left-turn-actors.jsonl").write_text("".join(
            json.dumps({"native_frame": 1000 + i, "time_s": i / 20}) + "\n"
            for i in range(600)))
        (self.root / "video_frames.jsonl").write_text("".join(
            json.dumps({"native_frame": 1000 + i, "video_frame": i,
                        "time_s": i / 20}) + "\n" for i in range(600)))
        with self.assertRaisesRegex(ValueError, "Missing required source: trace.jsonl"):
            source_join(self.root, {"source_kind": "original_native"})


if __name__ == "__main__":
    unittest.main()
