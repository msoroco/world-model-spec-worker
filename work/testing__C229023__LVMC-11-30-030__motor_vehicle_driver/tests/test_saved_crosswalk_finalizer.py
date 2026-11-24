import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from native_crosswalk_capture import CAMERAS, FRAME_COUNT, NativeCrosswalkRecorder
from test_native_crosswalk_capture import CASE, ACTORS, context, observations

spec = importlib.util.spec_from_file_location("saved_crosswalk_finalizer", HERE / "saved_crosswalk_finalizer.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SavedFinalizerTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        recorder = NativeCrosswalkRecorder(case_id=CASE, context=context(), actor_ids=ACTORS)
        for index in range(FRAME_COUNT):
            frame = 100 + index
            recorder.append(world_frame=frame, actors=observations(frame, -5.0 + .03 * index),
                            camera_frames={name: SimpleNamespace(frame=frame) for name in CAMERAS})
        recorder.write(self.root)
        self.media = {"videos": {name: {"frames": 900, "video_sha256": "a" * 64}
                                 for name in CAMERAS}}

    def test_saved_original_measurement_and_no_rewrite(self):
        with patch.object(module, "audit_video", return_value=self.media):
            report = module.finalize(directory=self.root, case_id=CASE)
        self.assertEqual(report["observed"]["rear_approach_sampled"], True)
        self.assertEqual(report["observed"]["ego_full_pass_sampled"], True)
        self.assertEqual(report["physical_acceptance"], "unverified")
        self.assertFalse(report["legal_verdict_claimed"])
        self.assertTrue(all(check["matched"] for check in report["target_checks"]))
        saved = json.loads((self.root / "crosswalk-measurement.json").read_text())
        self.assertEqual(saved["source_sha256"], report["source_sha256"])
        with self.assertRaisesRegex(ValueError, "prior finalization"):
            module.finalize(directory=self.root, case_id=CASE)

    def test_rejects_changed_source_and_media_count(self):
        changed = self.media.copy()
        changed["videos"] = {name: value.copy() for name, value in self.media["videos"].items()}
        changed["videos"]["overview"]["frames"] = 899
        with patch.object(module, "audit_video", return_value=changed):
            with self.assertRaisesRegex(ValueError, "frame counts differ"):
                module.finalize(directory=self.root, case_id=CASE)
        (self.root / "trace.jsonl").write_text((self.root / "trace.jsonl").read_text() + "{}\n")
        with patch.object(module, "audit_video", return_value=self.media):
            with self.assertRaisesRegex(ValueError, "source bytes changed"):
                module.finalize(directory=self.root, case_id=CASE)


if __name__ == "__main__":
    unittest.main()
