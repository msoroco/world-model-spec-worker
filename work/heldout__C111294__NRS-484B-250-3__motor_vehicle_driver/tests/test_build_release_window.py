import json
from pathlib import Path
import sys
import tempfile
import unittest

OWNER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OWNER))

from build_release_window import build
from qualitative_release_audit import audit


class BuildReleaseWindowTest(unittest.TestCase):
    def test_three_full_windows_and_tampered_original_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            proof = build(temp)
            roots = [Path(temp) / f"yield_release_delay-{index:04d}" for index in range(3)]
            self.assertEqual([p["subject_entry_frame"] - proof["points"][0]["subject_entry_frame"]
                              for p in proof["points"]], [0, 80, 160])
            for root in roots:
                self.assertEqual(len((root / "intersection_participants.jsonl").read_text().splitlines()), 320)
                self.assertEqual(len((root / "video_frames.jsonl").read_text().splitlines()), 320)
                self.assertEqual(len((root / "trace.jsonl").read_text().splitlines()), 320)
            original = roots[1] / "trace.jsonl"
            rows = [json.loads(line) for line in original.read_text().splitlines()]
            rows[100]["frame"] += 1
            original.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "frame-map or trace join failed"):
                audit(roots)


if __name__ == "__main__":
    unittest.main()
