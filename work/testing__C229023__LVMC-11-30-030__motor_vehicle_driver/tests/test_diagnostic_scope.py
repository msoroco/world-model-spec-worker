import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from canonical_evidence import project
from crosswalk_measurements import measure
from native_crosswalk_capture import CAMERAS, FRAME_COUNT, NativeCrosswalkRecorder
from saved_capture_audit import audit
from test_native_crosswalk_capture import ACTORS, CASE, context, observations


class DiagnosticScopeTests(unittest.TestCase):
    def test_marked_fixture_requires_explicit_mode_at_every_source_gate(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            recorder = NativeCrosswalkRecorder(case_id=CASE, context=context(), actor_ids=ACTORS)
            for index in range(FRAME_COUNT):
                frame = 40 + index
                recorder.append(world_frame=frame, actors=observations(frame, index / 10),
                                camera_frames={name: SimpleNamespace(frame=frame) for name in CAMERAS})
            recorder.write(root)
            receipt = root / "receipt.json"
            marked = json.loads(receipt.read_text())
            marked["diagnostic_fixture"] = True
            receipt.write_text(json.dumps(marked) + "\n")
            source = dict(case_id=CASE, context_path=root / "context.json",
                          trace_path=root / "trace.jsonl", receipt_path=receipt)
            with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
                measure(**source)
            with self.assertRaisesRegex(ValueError, "original exact-case receipt"):
                audit(directory=root, case_id=CASE)
            with self.assertRaisesRegex(ValueError, "exact sealed 900-frame"):
                project(root, CASE)
            measured = measure(**source, fixture_mode=True)
            self.assertEqual(measured["frame_count"], 900)
            self.assertEqual(audit(directory=root, case_id=CASE, fixture_mode=True)["frame_count"], 900)
            _, evidence, _ = project(root, CASE, fixture_mode=True)
            self.assertEqual(len(evidence), 9)
            self.assertEqual(measured["physical_acceptance"], "unverified")


if __name__ == "__main__":
    unittest.main()
