"""Exercise the pinned runtime Native exit and owner-release order."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work" / "c125714-2031-lifecycle-tests"
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))

from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, content in (("construction.json", "{}\n"), ("runner.py", "# fixture\n"),
                              ("trace.jsonl", "{}\n"), ("video_frames.jsonl", "{}\n"),
                              ("acquisition-provenance.json", '{"diagnostic_fixture":true}\n')):
            (self.root / name).write_text(content)

    def test_native_exit_then_owner_release_before_saved_processing(self):
        seal = seal_capture(self.root, frames=3, restoration={"restored": True},
                            errors=[], encoder_exit_codes={"overview": 0})
        self.assertEqual(seal["events"],
                         ["capture_finished", "encoders_closed", "restoration_verified"])
        native_exit = record_native_exit(self.root)
        self.assertEqual(native_exit["event"], "native_exit")
        receipt = self.root / "owner-release.json"
        owner = acknowledge_owner_release(self.root, receipt, True)
        self.assertEqual(owner["event"], "owner_released")
        _closure(self.root, receipt, "native", False)
        self.assertTrue(receipt.is_file())
        (self.root / "trace.jsonl").write_text('{"changed":true}\n')
        with self.assertRaisesRegex(ValueError, "Sealed original changed"):
            _closure(self.root, receipt, "native", False)

    def test_release_cannot_precede_native_exit(self):
        seal_capture(self.root, frames=3, restoration={"restored": True}, errors=[])
        with self.assertRaisesRegex(ValueError, "has not exited"):
            acknowledge_owner_release(self.root, self.root / "owner.json", True)


if __name__ == "__main__":
    unittest.main()
