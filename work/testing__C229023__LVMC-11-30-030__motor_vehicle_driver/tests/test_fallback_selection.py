import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from fallback_selection import evaluate
from native_crosswalk_capture import CAMERAS, FRAME_COUNT, NativeCrosswalkRecorder
from test_native_crosswalk_capture import ACTORS, CASE, context, observations


class SavedFallbackSelectionTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def record(self, *, pedestrian_x=7.0, ego_motion=True):
        recorder = NativeCrosswalkRecorder(case_id=CASE, context=context(), actor_ids=ACTORS)
        for index in range(FRAME_COUNT):
            frame = 40 + index
            row = observations(frame, index / 10 if ego_motion else 0.0)
            row["pedestrian"]["center"] = [pedestrian_x, 0.0]
            recorder.append(world_frame=frame, actors=row,
                            camera_frames={name: SimpleNamespace(frame=frame) for name in CAMERAS})
        recorder.write(self.root)

    def evaluate_saved(self):
        return evaluate(case_id=CASE, context_path=self.root / "context.json",
                        trace_path=self.root / "trace.jsonl", receipt_path=self.root / "receipt.json")

    def test_overlap_selects_new_slower_attempt(self):
        self.record()
        selected = self.evaluate_saved()
        self.assertEqual(selected["candidate_id"], "fallback1")
        self.assertTrue(selected["retry_trigger_met"])
        self.assertLessEqual(selected["ego_crossing_entry_frame"],
                             selected["pedestrian_clearance_last_frame"])
        self.assertLessEqual(selected["entry_minus_clearance_s"], 0.0)
        self.assertEqual(selected["physical_acceptance"], "unverified")

    def test_missing_pedestrian_or_entry_does_not_invent_trigger(self):
        self.record(pedestrian_x=20.0)
        self.assertEqual(self.evaluate_saved()["outcome"],
                         "insufficient_ego_entry_or_pedestrian_crossing")
        for path in self.root.iterdir():
            path.unlink()
        self.record(ego_motion=False)
        self.assertFalse(self.evaluate_saved()["retry_trigger_met"])

    def test_changed_original_source_rejected(self):
        self.record()
        path = self.root / "context.json"
        data = json.loads(path.read_text())
        data["crosswalk"]["polygon"][0][0] += 0.1
        path.write_text(json.dumps(data) + "\n")
        with self.assertRaisesRegex(ValueError, "source bytes changed"):
            self.evaluate_saved()


if __name__ == "__main__":
    unittest.main()
