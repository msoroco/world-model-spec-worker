import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from encode_original import VIEWS, audit_encoded_views, file_sha


class EncodedAuditTest(unittest.TestCase):
    def test_full_decode_and_changed_source_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            views = {}
            for camera, name in VIEWS.items():
                target = root / (name + ".mkv")
                subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                                "color=c=red:s=32x24:r=20", "-frames:v", "3",
                                "-c:v", "ffv1", str(target)], check=True)
                views[name] = {"source_camera": camera, "path": target.name,
                               "source": "original_png_index", "codec": "ffv1",
                               "fps": 20, "frames": 3, "sha256": file_sha(target)}
            (root / "encoded-views.json").write_text(json.dumps({"case_id": "exact-case", "views": views}))
            receipt = audit_encoded_views(root, 3)
            self.assertEqual(set(receipt["views"]), set(VIEWS.values()))
            self.assertTrue(all(v["frames_decoded"] == 3 for v in receipt["views"].values()))
            with self.assertRaisesRegex(ValueError, "source/cadence identity mismatch"):
                audit_encoded_views(root, 4)
            (root / "overview.mkv").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "overview encoded bytes changed"):
                audit_encoded_views(root, 3)


if __name__ == "__main__":
    unittest.main()
