import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_acquisition import seal_original_acquisition
from saved_delivery import CAMERAS, audit_saved
from test_native_acquisition import CASE, source_rows


class SavedDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        motion, context = source_rows()
        source = self.base / "original-context.json"
        source.write_text(json.dumps(context))
        self.acquisition = self.base / "acquisition"
        self.inventory = seal_original_acquisition(
            self.acquisition, CASE, motion, context,
            context_source={"path": str(source),
                            "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        )
        cameras = {}
        for camera in CAMERAS:
            path = self.acquisition / (camera + ".mkv")
            subprocess.run(
                ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                 "color=c=black:s=64x48:r=20", "-frames:v", "25", "-c:v", "ffv1",
                 str(path)], check=True, capture_output=True,
            )
            cameras[camera] = {"path": path.name,
                               "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "frame_ids": [row["frame_id"] for row in motion]}
        self.manifest = {"case_id": CASE, "source_kind": "original_live_native",
                         "diagnostic_fixture": False,
                         "frame_map_sha256": self.inventory["sources"]["frame_map"]["sha256"],
                         "cameras": cameras}
        self.write_manifest()

    def write_manifest(self):
        (self.acquisition / "camera-manifest.json").write_text(json.dumps(self.manifest))

    def test_full_saved_decode_and_source_binding(self):
        result = audit_saved(self.acquisition, CASE, minimum_frames=25)
        self.assertEqual(result["frame_count"], 25)
        self.assertEqual(set(result["cameras"]), set(CAMERAS))
        self.assertEqual(result["legal_prudence"], "unresolved")
        self.assertFalse(result["physical_visibility_reviewed"])
        with self.assertRaisesRegex(ValueError, "shorter"):
            audit_saved(self.acquisition, CASE)

    def test_rejects_camera_frame_gap_and_rebinding(self):
        self.manifest["cameras"]["approach"]["frame_ids"][4] += 1
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "frame join"):
            audit_saved(self.acquisition, CASE, minimum_frames=25)
        self.manifest["cameras"]["approach"]["frame_ids"][4] -= 1
        self.manifest["frame_map_sha256"] = "0" * 64
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "frame map"):
            audit_saved(self.acquisition, CASE, minimum_frames=25)

    def test_rejects_diagnostic_and_missing_camera(self):
        self.manifest["diagnostic_fixture"] = True
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "not an original"):
            audit_saved(self.acquisition, CASE, minimum_frames=25)
        self.manifest["diagnostic_fixture"] = False
        del self.manifest["cameras"]["overview"]
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "four original"):
            audit_saved(self.acquisition, CASE, minimum_frames=25)

    def test_rejects_tampered_media(self):
        (self.acquisition / "overview.mkv").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            audit_saved(self.acquisition, CASE, minimum_frames=25)

    def test_rejects_wrong_codec_even_with_updated_hash(self):
        path = self.acquisition / "overview.mkv"
        path.unlink()
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
             "color=c=black:s=64x48:r=20", "-frames:v", "25", "-c:v", "mpeg4",
             str(path)], check=True, capture_output=True,
        )
        self.manifest["cameras"]["overview"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "codec"):
            audit_saved(self.acquisition, CASE, minimum_frames=25)


if __name__ == "__main__":
    unittest.main()
