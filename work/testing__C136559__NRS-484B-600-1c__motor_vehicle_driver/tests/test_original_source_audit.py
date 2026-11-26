import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from original_source_audit import audit
import test_speed_source_review as speed_tests


class SourceDeliveryTests(unittest.TestCase):
    def make_attempt(self, root):
        case, inventory = speed_tests.OriginalSpeedReviewTests()._attempt(root)
        media = {}
        for name in ("overview", "approach", "reference_corner", "driver_reference"):
            path = root / (name + ".mkv")
            path.write_bytes(b"synthetic media marker; not decoded or accepted")
            media[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        trace = root / "trace.jsonl"
        trace.write_text('{"source":"synthetic"}\n')
        media["trace"] = {"path": trace.name, "sha256": hashlib.sha256(trace.read_bytes()).hexdigest()}
        inventory["media"] = media
        return case, inventory

    def test_source_inventory_requires_later_media_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self.make_attempt(root)
            receipt = audit(root, inventory, case)
            self.assertEqual(receipt["original_frames"], 900)
            self.assertFalse(receipt["full_video_decode_confirmed"])
            self.assertFalse(receipt["physical_completion_confirmed"])

    def test_missing_camera_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self.make_attempt(root)
            (root / "overview.mkv").unlink()
            with self.assertRaisesRegex(ValueError, "media source missing"):
                audit(root, inventory, case)

    def test_stale_trace_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self.make_attempt(root)
            (root / "trace.jsonl").write_text("changed")
            with self.assertRaisesRegex(ValueError, "empty or stale"):
                audit(root, inventory, case)

    def test_diagnostic_flag_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case, inventory = self.make_attempt(root)
            inventory["diagnostic_fixture"] = True
            with self.assertRaisesRegex(ValueError, "diagnostic fixture"):
                audit(root, inventory, case)
