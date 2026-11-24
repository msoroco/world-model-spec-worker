import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("saved_video_audit", HERE / "saved_video_audit.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SavedVideoAuditTests(unittest.TestCase):
    def test_real_full_decode_and_profile(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            path = Path(temporary) / "overview.mkv"
            frames = [bytes([n, 20, 30]) * 16 for n in (10, 40, 80)]
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "rawvideo",
                            "-pixel_format", "rgb24", "-video_size", "4x4", "-framerate", "20",
                            "-i", "pipe:0", "-c:v", "ffv1", str(path)],
                           input=b"".join(frames), check=True)
            self.assertEqual(module._probe(path)["codec_name"], "ffv1")
            decoded = module._decode(path, 4, 4, 3)
            self.assertEqual(decoded["frames"], 3)
            self.assertTrue(decoded["varied_frames"])
            self.assertEqual(decoded["rgb_sha256"], hashlib.sha256(b"".join(frames)).hexdigest())
            with self.assertRaisesRegex(ValueError, "incomplete decoded camera"):
                module._decode(path, 4, 4, 4)
            with self.assertRaisesRegex(ValueError, "extra decoded camera"):
                module._decode(path, 4, 4, 2)

    def test_audit_rejects_missing_and_wrong_profile(self):
        case = "testing__C229023__LVMC-11-30-030__motor_vehicle_driver__unmarked_pass"
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            capture = {"frame_count": 900, "frame_map_sha256": "x" * 64,
                       "first_native_frame": 100, "last_native_frame": 999}
            with patch.object(module, "audit_capture", return_value=capture):
                with self.assertRaisesRegex(ValueError, "original camera video missing"):
                    module.audit(directory=root, case_id=case)
                (root / "overview.mkv").write_bytes(b"video")
                with patch.object(module, "_probe", return_value={"codec_name": "h264", "width": 1920,
                                                                  "height": 1080, "avg_frame_rate": "20/1"}):
                    with self.assertRaisesRegex(ValueError, "encoding/profile differs"):
                        module.audit(directory=root, case_id=case)


if __name__ == "__main__":
    unittest.main()
