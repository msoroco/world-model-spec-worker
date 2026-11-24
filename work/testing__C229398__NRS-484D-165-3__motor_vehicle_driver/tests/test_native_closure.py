import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / "runtime" / "scenario_pipeline"))

import native_closure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ClosureTest(unittest.TestCase):
    def test_seals_only_verified_restored_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            capture = root / "capture"
            capture.mkdir()
            case_id = native_closure.ASSIGNMENT + "__dark_lamps_on"
            (capture / "capture-packet.json").write_text(json.dumps({
                "case_id": case_id, "frame_count": 900,
                "native_first_frame": 100, "native_last_frame": 999}) + "\n")
            for name in ("trace.jsonl", "video_frames.jsonl"):
                (root / name).write_text("{}\n" * 900)
            (root / "parked_lamp_observations.jsonl").write_text("{}\n" * 900)
            (root / "site_context.json").write_text("{}\n")
            (root / "runner.py").write_text("# source\n")
            (root / "construction.json").write_text(json.dumps({
                "recording_description": {"window": "45 seconds", "streams": []}}) + "\n")
            fake_views = {view: {"sha256": "a" * 64} for view in native_closure.VIEWS.values()}
            with patch.object(native_closure, "audit_encoded", return_value={
                "views": fake_views, "encoded_index_sha256": "b" * 64}):
                with self.assertRaisesRegex(ValueError, "verified world restoration"):
                    native_closure.close(root, "dark_lamps_on", "c" * 64, {"restored": False})
                self.assertFalse((root / "result.json").exists())
                sealed = native_closure.close(root, "dark_lamps_on", "c" * 64,
                                              {"restored": True, "method": "test readback"})
            self.assertEqual(sealed["events"], ["capture_finished", "encoders_closed",
                                                "restoration_verified"])
            self.assertEqual(sealed["sources"]["result.json"], sha(root / "result.json"))
            self.assertIsNone(json.loads((root / "result.json").read_text())
                              ["measured_values"]["lamp_visibility"])
            with self.assertRaisesRegex(ValueError, "retain previous Native closure"):
                native_closure.close(root, "dark_lamps_on", "c" * 64, {"restored": True})


if __name__ == "__main__":
    unittest.main()
