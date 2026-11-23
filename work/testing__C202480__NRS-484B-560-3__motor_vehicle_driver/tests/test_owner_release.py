"""Check Native process-generation release and stale receipt rejection."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from owner_release import release, same_process_alive, sha, verify_release
from runner import native_process_identity


class OwnerReleaseTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / ".runtime-work"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name) / "attempt"
        self.attempt.mkdir()
        self.identity = native_process_identity()
        self.status_path = self.attempt / "native-run-status.json"
        self.status_path.write_text(json.dumps({
            "case_id": "diagnostic", "errors": [], "capture": {"frames": 900},
            "restoration": {"restored": True},
            "native_process": self.identity}))
        (self.attempt / "native-exit.json").write_text(json.dumps({
            "event": "native_exit_pending_process_termination",
            "case_id": "diagnostic", "native_process": self.identity,
            "native_run_status_sha256": sha(self.status_path)}))

    def test_live_original_process_cannot_be_released(self):
        self.assertTrue(same_process_alive(self.identity))
        with self.assertRaisesRegex(ValueError, "still running"):
            release(self.attempt)
        self.assertFalse((self.attempt / "owner-release.json").exists())

    def test_release_after_exit_and_reject_changed_status(self):
        released = release(self.attempt, liveness_probe=lambda _: False)
        self.assertEqual(released["event"], "owner_released")
        self.assertEqual(verify_release(self.attempt, liveness_probe=lambda _: False),
                         released)
        with self.assertRaisesRegex(ValueError, "still live"):
            verify_release(self.attempt)
        self.status_path.write_text(self.status_path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "identity differs"):
            verify_release(self.attempt, liveness_probe=lambda _: False)


if __name__ == "__main__":
    unittest.main()
