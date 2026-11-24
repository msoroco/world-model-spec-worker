import copy
import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("saved_delivery", ROOT / "saved_delivery.py")
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
from freight_contract import SourceError
from test_saved_comparison import fixture


def packet(root):
    manifest = fixture(root / "sources", "freight_loading")
    manifest.update(job_id="job-1", attempt_id="attempt-1", recording_id="recording-1",
                    native_result_sha256=manifest["sources"]["native_result"]["sha256"])
    media = {}
    for name in delivery.CAMERAS:
        path = root / (name + ".mp4")
        path.write_bytes((name + " fixture bytes").encode())
        media[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest["media"] = media
    return manifest


def fake_probe(path):
    width, height = delivery.CAMERAS[path.stem]
    return {"width": width, "height": height, "r_frame_rate": "20/1", "nb_read_frames": "900"}


class SavedDeliveryTests(unittest.TestCase):
    def test_exact_original_delivery_checks_all_sources_and_four_cameras(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = delivery.audit_delivery(packet(root), attempt_root=root, media_probe=fake_probe)
            self.assertEqual(result["frames_checked"], 900)
            self.assertEqual(set(result["media_sha256"]), set(delivery.CAMERAS))
            self.assertTrue(result["source_integrity"])
            self.assertFalse(result["actual_pixels_reviewed"])

    def test_rejects_diagnostic_foreign_case_and_media_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = packet(root)
            bad = copy.deepcopy(original)
            bad["acquisition_kind"] = "diagnostic"
            with self.assertRaisesRegex(SourceError, "diagnostic"):
                delivery.audit_delivery(bad, attempt_root=root, media_probe=fake_probe)
            bad = copy.deepcopy(original)
            bad["case_id"] = "foreign"
            with self.assertRaisesRegex(SourceError, "foreign delivery"):
                delivery.audit_delivery(bad, attempt_root=root, media_probe=fake_probe)
            (root / "overview.mp4").write_bytes(b"tampered")
            with self.assertRaisesRegex(SourceError, "stale media"):
                delivery.audit_delivery(original, attempt_root=root, media_probe=fake_probe)

    def test_rejects_escape_missing_camera_and_bad_media_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = packet(root)
            bad = copy.deepcopy(original)
            bad["media"]["overview"]["path"] = "../outside.mp4"
            with self.assertRaises((SourceError, FileNotFoundError)):
                delivery.audit_delivery(bad, attempt_root=root, media_probe=fake_probe)
            bad = copy.deepcopy(original)
            del bad["media"]["approach"]
            with self.assertRaisesRegex(SourceError, "four original"):
                delivery.audit_delivery(bad, attempt_root=root, media_probe=fake_probe)
            def short_video(path):
                info = fake_probe(path)
                info["nb_read_frames"] = "899"
                return info
            with self.assertRaisesRegex(SourceError, "wrong camera frame count"):
                delivery.audit_delivery(original, attempt_root=root, media_probe=short_video)


if __name__ == "__main__":
    unittest.main()
