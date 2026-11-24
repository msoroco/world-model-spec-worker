import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saved_cameras import SavedCameraError, audit


def seal(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SavedCameraTest(unittest.TestCase):
    def fixture(self, root):
        native_path = root / "native.json"
        native_path.write_text(json.dumps({"case_id": "exact", "frames": [
            {"frame": 20, "time_s": 1.0}, {"frame": 21, "time_s": 1.05}]}))
        views = {}
        for name in ("overview", "approach", "reference_corner", "driver_reference"):
            rows = []
            for frame, time_s in ((20, 1.0), (21, 1.05)):
                path = root / f"{name}-{frame}.png"
                Image.new("RGB", (3, 2), (frame, 10, 10)).save(path)
                rows.append({"frame": frame, "time_s": time_s,
                             "path": str(path), "sha256": seal(path)})
            views[name] = rows
        manifest = {"case_id": "exact", "native_sha256": seal(native_path),
                    "frame_count": 2, "fps": 20, "views": views}
        manifest_path = root / "camera-manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        return native_path, manifest_path, manifest

    def invoke(self, native_path, manifest_path):
        return audit(native_path, seal(native_path), manifest_path, seal(manifest_path),
                     expected_case="exact", expected_count=2,
                     expected_views={name: (3, 2) for name in
                                     ("overview", "approach", "reference_corner", "driver_reference")})

    def test_decodes_all_source_images_with_frame_join(self):
        with tempfile.TemporaryDirectory() as directory:
            native_path, manifest_path, _ = self.fixture(Path(directory))
            result = self.invoke(native_path, manifest_path)
            self.assertEqual(sum(v["decoded_original_pngs"] for v in result["source_decode"].values()), 8)
            self.assertEqual(result["physical_visibility"], "unreviewed")

    def test_rejects_wrong_frame_and_missing_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            native_path, manifest_path, manifest = self.fixture(Path(directory))
            manifest["views"]["approach"][1]["frame"] = 22
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(SavedCameraError, "frame/time join"):
                self.invoke(native_path, manifest_path)
        with tempfile.TemporaryDirectory() as directory:
            native_path, manifest_path, manifest = self.fixture(Path(directory))
            image_path = Path(manifest["views"]["overview"][0]["path"])
            Image.new("RGB", (3, 2), (0, 0, 0)).save(image_path)
            manifest["views"]["overview"][0]["sha256"] = seal(image_path)
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(SavedCameraError, "all-zero"):
                self.invoke(native_path, manifest_path)

    def test_rejects_stale_image_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            native_path, manifest_path, manifest = self.fixture(Path(directory))
            Path(manifest["views"]["overview"][0]["path"]).write_bytes(b"changed")
            with self.assertRaisesRegex(SavedCameraError, "original hash"):
                self.invoke(native_path, manifest_path)

    def test_original_path_must_be_attempt_local_camera_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            native_path, manifest_path, _ = self.fixture(Path(directory))
            with self.assertRaisesRegex(SavedCameraError, "original path differs"):
                audit(native_path, seal(native_path), manifest_path, seal(manifest_path),
                      expected_case="exact", expected_count=2, strict_paths=True,
                      expected_views={name: (3, 2) for name in
                                      ("overview", "approach", "reference_corner", "driver_reference")})
